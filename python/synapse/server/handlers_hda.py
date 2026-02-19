"""
Synapse HDA Handler Mixin

Handlers for Houdini Digital Asset (HDA) creation, parameter promotion,
help documentation, and high-level packaging from AI prompts.
"""

import os
import time
from typing import Dict

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from .handler_helpers import _HOUDINI_UNAVAILABLE

# Valid HDA categories — Houdini's node context names
_VALID_CATEGORIES = frozenset({
    "Sop", "Object", "Driver", "Lop", "Top",
    "Dop", "Cop2", "Chop", "Vop", "Shop",
})


class HdaHandlerMixin:
    """Mixin providing HDA creation, parameter promotion, help, and packaging handlers."""

    def _handle_hda_create(self, payload: Dict) -> Dict:
        """Convert a subnet into a Houdini Digital Asset (HDA).

        Wraps node.createDigitalAsset() with metadata setup and file installation.
        The entire operation runs inside an undo group for safe rollback.

        Payload:
            subnet_path (str, required): Path to the subnet node to convert.
            operator_name (str, required): Internal operator type name (e.g. 'my_tool').
            operator_label (str, required): Human-readable label (e.g. 'My Tool').
            category (str, required): Node category — Sop, Object, Driver, Lop, Top, etc.
            version (str): SemVer version string (default: '1.0.0').
            save_path (str, required): File path to save the .hda file.
            min_inputs (int): Minimum number of inputs (default: 0).
            max_inputs (int): Maximum number of inputs (default: 1).
            icon (str): Optional icon name (e.g. 'SOP_subnet').
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        subnet_path = resolve_param(payload, "subnet_path")
        operator_name = resolve_param(payload, "operator_name")
        operator_label = resolve_param(payload, "operator_label")
        category = resolve_param(payload, "category")
        version = resolve_param_with_default(payload, "version", "1.0.0")
        save_path = resolve_param(payload, "save_path")
        min_inputs = int(resolve_param_with_default(payload, "min_inputs", 0))
        max_inputs = int(resolve_param_with_default(payload, "max_inputs", 1))
        icon = resolve_param_with_default(payload, "icon", None)

        # Validate category
        if category not in _VALID_CATEGORIES:
            raise ValueError(
                f"'{category}' isn't a valid HDA category -- "
                f"use one of: {', '.join(sorted(_VALID_CATEGORIES))}"
            )

        from .main_thread import run_on_main

        def _on_main():
            node = hou.node(subnet_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find subnet at {subnet_path} -- "
                    "make sure the path points to an existing subnet node"
                )

            with hou.undos.group("synapse_hda_create"):
                # Build the full operator type: category/operator_name
                full_type = f"{category}/{operator_name}"

                hda_node = node.createDigitalAsset(
                    name=operator_name,
                    hda_file_name=save_path,
                    description=operator_label,
                    min_num_inputs=min_inputs,
                    max_num_inputs=max_inputs,
                )

                # Set metadata on the HDA definition
                definition = hda_node.type().definition()
                if definition is not None:
                    definition.setVersion(version)
                    definition.setComment(operator_label)
                    # Set extra metadata via sections or info
                    try:
                        definition.setExtraInfo(
                            f"author=synapse;version={version};"
                            f"created={time.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                    except Exception:
                        pass  # Extra info is best-effort

                    if icon:
                        try:
                            definition.setIcon(icon)
                        except Exception:
                            pass  # Icon setting is best-effort

                # Install the HDA file
                hou.hda.installFile(save_path)

            return {
                "status": "ok",
                "hda_path": hda_node.path(),
                "operator_type": full_type,
                "save_path": save_path,
            }

        return run_on_main(_on_main)

    def _handle_hda_promote_parm(self, payload: Dict) -> Dict:
        """Promote an internal node parameter to the HDA interface.

        Uses hou.HDADefinition.setParmTemplateGroup() to modify the HDA's
        parameter interface. Creates channel references from the promoted
        parameter to the internal node parameter.

        Idempotent: re-promoting the same parameter updates rather than duplicates.

        Payload:
            hda_path (str, required): Path to the HDA instance node.
            internal_node (str, required): Relative path to internal node (e.g. 'scatter1').
            parm_name (str, required): Parameter name on the internal node.
            label (str): Optional label override for the promoted parameter.
            folder (str): Optional folder/tab name to place the parameter in.
            callback (str): Optional Python callback script.
            conditions (dict): Optional visibility conditions.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        hda_path = resolve_param(payload, "hda_path")
        internal_node_name = resolve_param(payload, "internal_node")
        parm_name = resolve_param(payload, "parm_name")
        label = resolve_param_with_default(payload, "label", None)
        folder = resolve_param_with_default(payload, "folder", None)
        callback = resolve_param_with_default(payload, "callback", None)
        conditions = resolve_param_with_default(payload, "conditions", None)

        from .main_thread import run_on_main

        def _on_main():
            hda_node = hou.node(hda_path)
            if hda_node is None:
                raise ValueError(
                    f"Couldn't find HDA node at {hda_path} -- "
                    "make sure the path points to an existing HDA instance"
                )

            definition = hda_node.type().definition()
            if definition is None:
                raise ValueError(
                    f"The node at {hda_path} doesn't appear to be an HDA -- "
                    "it has no HDA definition attached"
                )

            # Find the internal node
            internal_node = hda_node.node(internal_node_name)
            if internal_node is None:
                raise ValueError(
                    f"Couldn't find internal node '{internal_node_name}' inside "
                    f"{hda_path} -- check the relative path"
                )

            # Find the parameter on the internal node
            source_parm = internal_node.parm(parm_name)
            if source_parm is None:
                raise ValueError(
                    f"Couldn't find parameter '{parm_name}' on "
                    f"{internal_node.path()} -- check the parameter name"
                )

            # Get the parameter template from the source
            source_template = source_parm.parmTemplate()

            # Build the promoted parameter template
            promoted_name = f"{internal_node_name}_{parm_name}"
            promoted_label = label or source_template.label()

            # Clone the template with the new name
            promoted_template = source_template.clone()
            promoted_template.setName(promoted_name)
            promoted_template.setLabel(promoted_label)

            if callback:
                promoted_template.setScriptCallback(callback)
                promoted_template.setScriptCallbackLanguage(
                    hou.scriptLanguage.Python
                )

            # Get the current parm template group
            ptg = definition.parmTemplateGroup()

            # Check for idempotent update -- remove existing if present
            existing = ptg.find(promoted_name)
            if existing is not None:
                ptg.remove(promoted_name)

            # Add to folder if specified, otherwise add to root
            if folder:
                folder_template = ptg.findFolder(folder)
                if folder_template is None:
                    # Create the folder
                    new_folder = hou.FolderParmTemplate(
                        folder.lower().replace(" ", "_"),
                        folder,
                    )
                    new_folder.addParmTemplate(promoted_template)
                    ptg.append(new_folder)
                else:
                    ptg.appendToFolder(folder_template, promoted_template)
            else:
                ptg.append(promoted_template)

            # Apply the updated template group
            definition.setParmTemplateGroup(ptg)

            # Create channel reference from promoted parm to internal parm
            promoted_parm = hda_node.parm(promoted_name)
            if promoted_parm is not None:
                source_parm.set(
                    promoted_parm,
                    language=hou.exprLanguage.Hscript,
                    follow_parm_reference=False,
                )

            return {
                "status": "ok",
                "promoted_parm": promoted_name,
                "folder": folder or "(root)",
            }

        return run_on_main(_on_main)

    def _handle_hda_set_help(self, payload: Dict) -> Dict:
        """Set help documentation on an HDA.

        Generates Houdini wiki markup help content from structured inputs
        and stores it via HDA definition sections.

        Payload:
            hda_path (str, required): Path to the HDA instance node.
            summary (str): Short summary for the HDA.
            description (str): Full description (supports Houdini wiki markup).
            parameters_help (dict): Mapping of {parm_name: help_text}.
            tips (list): List of tip strings.
            author (str): Author name.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        hda_path = resolve_param(payload, "hda_path")
        summary = resolve_param_with_default(payload, "summary", None)
        description = resolve_param_with_default(payload, "description", None)
        parameters_help = resolve_param_with_default(payload, "parameters_help", None)
        tips = resolve_param_with_default(payload, "tips", None)
        author = resolve_param_with_default(payload, "author", None)

        from .main_thread import run_on_main

        def _on_main():
            hda_node = hou.node(hda_path)
            if hda_node is None:
                raise ValueError(
                    f"Couldn't find HDA node at {hda_path} -- "
                    "make sure the path points to an existing HDA instance"
                )

            definition = hda_node.type().definition()
            if definition is None:
                raise ValueError(
                    f"The node at {hda_path} doesn't appear to be an HDA -- "
                    "it has no HDA definition attached"
                )

            # Set the comment/summary
            if summary:
                definition.setComment(summary)

            # Build help card content in Houdini wiki markup
            help_lines = []

            if summary:
                help_lines.append(f"= {summary} =")
                help_lines.append("")

            if description:
                help_lines.append("#type: node")
                help_lines.append(f"#context: {definition.nodeTypeCategory().name()}")
                help_lines.append("")
                help_lines.append(description)
                help_lines.append("")

            if author:
                help_lines.append(f"@author {author}")
                help_lines.append("")

            if parameters_help and isinstance(parameters_help, dict):
                help_lines.append("@parameters")
                help_lines.append("")
                for pname, phelp in sorted(parameters_help.items()):
                    help_lines.append(f"{pname}:")
                    help_lines.append(f"    {phelp}")
                    help_lines.append("")

            if tips and isinstance(tips, list):
                help_lines.append("TIP:")
                for tip in tips:
                    help_lines.append(f"    * {tip}")
                help_lines.append("")

            help_content = "\n".join(help_lines)

            # Set help via the DialogScript section
            if help_content.strip():
                sections = definition.sections()
                # Use the standard help section name
                definition.addSection("HelpText", help_content)

            return {
                "status": "ok",
                "help_set": True,
            }

        return run_on_main(_on_main)

    def _handle_hda_package(self, payload: Dict) -> Dict:
        """High-level orchestrator: create subnet, build HDA, promote params, set help.

        Runs the entire pipeline inside a single undo group for atomic rollback
        on failure. This is the go-to tool for creating HDAs from a description.

        Payload:
            description (str, required): What the HDA should do.
            name (str, required): Operator name (e.g. 'scatter_on_surface').
            category (str, required): Node category (Sop, Object, Driver, Lop, Top).
            save_path (str, required): File path to save the .hda file.
            inputs (list): List of input descriptions (optional).
            promoted_parms (list): List of {node, parm, label} dicts (optional).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        description = resolve_param(payload, "description")
        name = resolve_param(payload, "name")
        category = resolve_param(payload, "category")
        save_path = resolve_param(payload, "save_path")
        inputs = resolve_param_with_default(payload, "inputs", None) or []
        promoted_parms = resolve_param_with_default(payload, "promoted_parms", None) or []

        # Validate category
        if category not in _VALID_CATEGORIES:
            raise ValueError(
                f"'{category}' isn't a valid HDA category -- "
                f"use one of: {', '.join(sorted(_VALID_CATEGORIES))}"
            )

        from .main_thread import run_on_main, _SLOW_TIMEOUT

        def _on_main():
            # Map category to parent container path
            category_parents = {
                "Sop": "/obj",
                "Object": "/obj",
                "Driver": "/out",
                "Lop": "/stage",
                "Top": "/obj",
                "Dop": "/obj",
            }
            parent_path = category_parents.get(category, "/obj")
            parent_node = hou.node(parent_path)
            if parent_node is None:
                raise ValueError(
                    f"Couldn't find parent context at {parent_path} -- "
                    "the scene may not have this context available"
                )

            needs_rollback = False
            rollback_exc = None

            with hou.undos.group("synapse_hda_package"):
                try:
                    # Step 1: Create a temporary container and subnet
                    if category == "Sop":
                        container = parent_node.createNode("geo", f"temp_{name}")
                        subnet = container.createNode("subnet", name)
                    else:
                        subnet = parent_node.createNode("subnet", name)
                        container = None

                    # Configure inputs
                    num_inputs = len(inputs) if inputs else 1
                    max_inputs = max(num_inputs, 1)

                    # Step 2: Create the HDA from the subnet
                    label = name.replace("_", " ").title()
                    hda_node = subnet.createDigitalAsset(
                        name=name,
                        hda_file_name=save_path,
                        description=label,
                        min_num_inputs=0,
                        max_num_inputs=max_inputs,
                    )

                    # Set metadata
                    definition = hda_node.type().definition()
                    if definition is not None:
                        definition.setVersion("1.0.0")
                        definition.setComment(description)
                        try:
                            definition.setExtraInfo(
                                f"author=synapse;version=1.0.0;"
                                f"created={time.strftime('%Y-%m-%d %H:%M:%S')};"
                                f"description={description[:200]}"
                            )
                        except Exception:
                            pass

                    # Install the HDA
                    hou.hda.installFile(save_path)

                    # Step 3: Promote parameters
                    promoted_count = 0
                    if promoted_parms and definition is not None:
                        ptg = definition.parmTemplateGroup()

                        for parm_spec in promoted_parms:
                            node_name = parm_spec.get("node", "")
                            parm_name_val = parm_spec.get("parm", "")
                            parm_label = parm_spec.get("label", "")

                            if not node_name or not parm_name_val:
                                continue

                            internal = hda_node.node(node_name)
                            if internal is None:
                                continue

                            src_parm = internal.parm(parm_name_val)
                            if src_parm is None:
                                continue

                            src_template = src_parm.parmTemplate()
                            promoted_name = f"{node_name}_{parm_name_val}"
                            promo_template = src_template.clone()
                            promo_template.setName(promoted_name)
                            promo_template.setLabel(
                                parm_label or src_template.label()
                            )

                            # Remove existing to avoid duplicates
                            existing = ptg.find(promoted_name)
                            if existing is not None:
                                ptg.remove(promoted_name)

                            ptg.append(promo_template)
                            promoted_count += 1

                        definition.setParmTemplateGroup(ptg)

                    # Step 4: Set help
                    if definition is not None:
                        help_lines = [
                            f"= {label} =",
                            "",
                            description,
                            "",
                        ]
                        if inputs:
                            help_lines.append("@inputs")
                            help_lines.append("")
                            for i, inp_desc in enumerate(inputs):
                                help_lines.append(f"Input {i + 1}:")
                                help_lines.append(f"    {inp_desc}")
                            help_lines.append("")

                        definition.addSection(
                            "HelpText", "\n".join(help_lines)
                        )

                    # Clean up temp container if we created one
                    if container is not None:
                        # The HDA node is now inside the container;
                        # move it out if needed, but typically it stays
                        pass

                except Exception as exc:
                    needs_rollback = True
                    rollback_exc = exc

            if needs_rollback:
                try:
                    hou.undos.performUndo()
                except Exception:
                    pass
                raise rollback_exc

            return {
                "status": "ok",
                "hda_path": hda_node.path(),
                "operator_type": f"{category}/{name}",
                "promoted_count": promoted_count,
                "save_path": save_path,
            }

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT)
