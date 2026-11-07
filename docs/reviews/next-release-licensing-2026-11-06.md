# Commercial-use review — OpenCV 5.1 GPU vision for SYNAPSE

**Status:** engineering review, not legal advice. Every licence statement below
carries the URL it was read at on 2026-11-06. Items that could not be read are
marked **UNVERIFIED** rather than filled in from memory.

**Question:** if SYNAPSE ships a supervised OpenCV 5.1 GPU vision worker —
CUDA-built, bundled with a commercial Windows product — what obligations exist,
and does anything block commercial distribution?

---

## 1. What SYNAPSE itself is

`LICENSE` at this tree is **MIT**, `Copyright (c) 2025-2026 Joseph Ibrahim`.
Commercial distribution of the repository's own code is already permitted; the
only duty is that the copyright and permission notice travel with substantial
portions.

So the question is not whether SYNAPSE may be sold. It is what the new
dependencies add.

## 2. The dependency table

| Component | Licence | Decisive condition for a shipped binary |
|---|---|---|
| OpenCV 5.1.0 | **Apache-2.0** — [LICENSE](https://github.com/opencv/opencv/blob/5.x/LICENSE) | Licence copy, mark modified files, carry NOTICE if one ships. Patent grant §3 terminates only if you sue over the Work |
| opencv_contrib CUDA modules (`cudaarithm`, `cudafilters`, `cudaimgproc`) | **Apache-2.0** — [LICENSE](https://github.com/opencv/opencv_contrib/blob/5.x/LICENSE) | Same terms. The modules disable themselves without CUDA and link `CUDA::cudart` and the `npp*` libraries — those are NVIDIA's, not Apache's |
| NVIDIA CUDA runtime (`cudart`, `cublas`, `cufft`, `npp*`) | **NVIDIA Software License Agreement + CUDA Toolkit Supplement** — [EULA](https://docs.nvidia.com/cuda/eula/index.html) | Only binaries listed in Attachment A may be redistributed; they must be part of an application with "material additional functionality"; no standalone redistribution; use limited to systems with NVIDIA GPUs |
| opencv-python wheels | Apache-2.0 (scripts MIT) — [PyPI](https://pypi.org/project/opencv-python/) | The official wheels are **CPU-only**; they also bundle FFmpeg (LGPLv2.1) and, on non-headless Linux, Qt 5 (LGPLv3) |
| OpenCV non-free contrib modules | Part of opencv_contrib — [modules README](https://github.com/opencv/opencv_contrib/blob/5.x/modules/README.md) | SURF, BRIEF, Censure, Freak, LUCID, Daisy, Self-similar are excluded from distributed builds as patented/non-free. SIFT is now included (patent expired) |
| OpenEXR | **BSD-3-Clause** — [LICENSE](https://github.com/AcademySoftwareFoundation/openexr/blob/main/LICENSE.md) | Reproduce the notice in documentation or accompanying materials |
| OpenImageIO | **Apache-2.0** — [LICENSE](https://github.com/AcademySoftwareFoundation/OpenImageIO/blob/main/LICENSE.md) | Same duties as OpenCV |
| numpy | **BSD-3-Clause** — [LICENSE](https://github.com/numpy/numpy/blob/main/LICENSE.txt) | Notice in documentation |
| PySide6 / Qt for Python | **LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only**, or commercial — [PyPI](https://pypi.org/project/PySide6/), [LGPLv3](https://www.gnu.org/licenses/lgpl-3.0.html) | LGPLv3 §4: prominent notice, licence texts, and relinkability (§4.d) — ship Qt as replaceable DLLs |

## 3. What actually creates work

Permissive licences (Apache-2.0, BSD-3) impose paperwork, not control: a
`THIRD_PARTY_NOTICES.md`, copies of the licence texts, and a statement of any
files modified. None of them reaches SYNAPSE's source.

Three items are different:

**NVIDIA's EULA is a contract, not a licence.** It permits redistributing the
Attachment A runtime binaries, on conditions: the application must do materially
more than the SDK, the SDK portions must only be accessed by the application,
the toolkit itself must not be redistributed, and the SDK is licensed for use
"only for use in systems with NVIDIA GPUs". The last clause is the one to put in
front of counsel if a CPU edition ships alongside the GPU one — the CPU build
does not ship CUDA at all, which is the clean answer, but the product-level
statement should be deliberate.

**PySide6's LGPLv3 is the largest pre-existing obligation.** It predates this
blueprint. §4.d is the clause closed-source desktop apps breach: the user must
be able to replace the Qt libraries with a modified, interface-compatible
version. Shipping Qt as separate DLLs beside the executable satisfies it;
one-file bundling that hides them does not. A Qt commercial licence removes the
question. This is not caused by OpenCV, but a commercial release review that
looks only at OpenCV will miss it.

**Build route decides what travels.** `opencv-python` wheels are CPU-only, so
they cannot satisfy the GPU requirement at all. Building OpenCV 5.1 from source
with CUDA is the only route to the required capability, and it also removes the
wheels' bundled FFmpeg from the dependency graph. That is the recommendation:
build, pin the build (the blueprint's commit candidates), and ship the NVIDIA
runtime binaries under Attachment A with the EULA notice.

**Non-free modules stay off.** The default build excludes them; keep it that
way, and record `OPENCV_ENABLE_NONFREE=OFF` in the build lock. The exact default
flag value is **UNVERIFIED** — the configuration reference returned HTTP 403
during this review — so the build lock should assert the flag rather than assume
it.

## 4. Obligations checklist for the release

- [ ] `installer/licenses/THIRD_PARTY_NOTICES.md` lists every shipped binary
      with licence, version and source revision.
- [ ] Apache-2.0 and BSD-3 licence texts ship with the payload.
- [ ] NVIDIA Attachment A binaries are named, and the EULA text ships with them.
- [ ] No CUDA Toolkit installer or unlisted NVIDIA file is inside the payload.
- [ ] `OPENCV_ENABLE_NONFREE=OFF` asserted in the build lock.
- [ ] Qt DLLs shipped replaceable; GPLv3 + LGPLv3 texts included; no one-file
      bundling of Qt.
- [ ] Worker build lock records compiler, CUDA version, module flags, commits
      and final file digests (the blueprint's §10 identity list).
- [ ] The CPU edition, if any, is described as containing no CUDA binaries.

## 5. Verdict

**No licence conflict blocks commercial use of OpenCV 5.1 GPU vision in
SYNAPSE.** The permissive licences ask for notices. NVIDIA's EULA asks for
disciplined packaging and a GPU-only reading. The LGPL asks for a Qt packaging
audit that SYNAPSE already owed before this release.

The engineering consequence is small and concrete: build OpenCV from source with
CUDA, pin the build, ship listed runtime binaries with notices, and treat the
licence checklist as a release gate rather than a documentation chore.

**What this review does not establish:** that OpenCV 5.1 builds on this machine,
that the CUDA modules execute, or that any NVIDIA binary is redistributable in a
particular jurisdiction. Those are WP1's receipts and counsel's call.
