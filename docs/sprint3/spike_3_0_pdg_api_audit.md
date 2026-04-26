# Spike 3.0 — PDG API Audit (Empirical)

> **Authority:** ARCHITECT scaffold (this doc) + Joe (operator, live
> Houdini). The script ``spike_3_0_pdg_audit_script.py`` runs inside
> graphical Houdini 21.0.671; this doc is the receiving vessel for
> its output. Spike 3.0 closes when Joe runs the script and pastes
> findings into §2–§4 below.
>
> **Status:** Audit landed 2026-04-26. §3 + §4 populated from
> audit output. Spike 3.1 design unblocked.
>
> **Sprint position:** Spike 3.0 is BLOCKING — Spike 3.1
> (TopsEventBridge) does not open until §4 is filled in. Anchors:
> ``CONTINUATION_INSIDE_OUT_TOPS.md`` § Hard API verification gate;
> Sprint 3 hard invariant #6.

---

## 0. Audit metadata

| Field | Value |
|---|---|
| Audit run | 2026-04-26T10:44:22 (local) |
| Houdini build | 21.0.671 |
| Python version | 3.11.7 |
| Operator | Joe Ibrahim |
| Script run | ``docs/sprint3/spike_3_0_pdg_audit_script.py`` |
| Full report file | ``C:\Users\User\spike_3_0_pdg_audit_20260426-104422.txt`` |
| Audit summary | 14 surfaces resolved · 6 missing · 0 errors |

---

## 1. Why this audit exists

Houdini 21.0.671 has known divergences from prior versions and from
external-LLM training data. The codebase has already pinned three:
``componentbuilder`` is not a native HDA, ``hou.secure`` is absent
(env-var fallback documented in ``spike_2_4_design.md`` §8), and
light nodes use ``xn__`` parameter prefix encoding.

The PDG / TOPs surface has its own divergences. ``shared/bridge.py:568``
records one:

> *H21 moved PDG events from ``hou.pdgEventType`` to the standalone
> ``pdg`` module. Cook events use ``pdg.GraphContext.addEventHandler``
> with ``pdg.PyEventHandler`` instead of ``hou TopNode.addEventCallback``
> (which handles ``hou.nodeEventType``).*

The early ``TopsEventBridge`` sketch in
``CONTINUATION_INSIDE_OUT_TOPS.md`` (lines ~186–280) reaches for
``hou.pdg.scheduler``, ``hou.pdg.workItem``, and
``hou.pdg.GraphContext``. The R8 implementation in ``bridge.py``
reaches for **standalone ``pdg``** instead. Until this audit
resolves which surface is real for what, Spike 3.1 cannot land code
that survives first contact with Houdini.

Sprint 3 hard invariant #6:

> *Hard API verification before any Houdini call: ``dir()``
> introspection in live Houdini 21.0.671 first, blueprint code
> second.*

---

## 2. Resolved surfaces

Raw audit output pasted verbatim. Annotations belong in §3.

### 2.1 hou.pdg surface

**Resolved path:** ``hou.pdg``

**STATUS:** NOT RESOLVABLE — ``hou.pdg`` does not exist.

Spike 3.1 cannot reference this name. If the bridge sketch uses it, the sketch needs revision.

### 2.2 Standalone `pdg` module surface

**Resolved path:** ``pdg``

**STATUS:** RESOLVED
**Type:** ``module``
**Repr:** ``<module 'pdg' from 'C:\\PROGRA~1/SIDEEF~1/HOUDIN~1.671/houdini/python3.11libs\\pdg\\__init__.py'>``

**__doc__:**
```
Python bindings for the PDG library.
```

**dir() — 234 attributes:**
```
  ActiveItemBlock<no signature: pybind11_type>  -> pybind11_type
  AddDependencyResult<no signature: pybind11_type>  -> pybind11_type
  AddNodeResult<no signature: pybind11_type>  -> pybind11_type
  AddParameterResult<no signature: pybind11_type>  -> pybind11_type
  AddSchedulerResult<no signature: pybind11_type>  -> pybind11_type
  AttribError<no signature: type>  -> type
  AttributeConfig<no signature: pybind11_type>  -> pybind11_type
  AttributeDictionary<no signature: pybind11_type>  -> pybind11_type
  AttributeDictionaryBase<no signature: pybind11_type>  -> pybind11_type
  AttributeFile<no signature: pybind11_type>  -> pybind11_type
  AttributeFileBase<no signature: pybind11_type>  -> pybind11_type
  AttributeFloat<no signature: pybind11_type>  -> pybind11_type
  AttributeFloatBase<no signature: pybind11_type>  -> pybind11_type
  AttributeGeometry<no signature: pybind11_type>  -> pybind11_type
  AttributeGeometryBase<no signature: pybind11_type>  -> pybind11_type
  AttributeInfo<no signature: pybind11_type>  -> pybind11_type
  AttributeInt<no signature: pybind11_type>  -> pybind11_type
  AttributeIntBase<no signature: pybind11_type>  -> pybind11_type
  AttributeOwner<no signature: pybind11_type>  -> pybind11_type
  AttributePattern<no signature: pybind11_type>  -> pybind11_type
  AttributePyObject<no signature: pybind11_type>  -> pybind11_type
  AttributePyObjectBase<no signature: pybind11_type>  -> pybind11_type
  AttributeSplit<no signature: pybind11_type>  -> pybind11_type
  AttributeString<no signature: pybind11_type>  -> pybind11_type
  AttributeStringBase<no signature: pybind11_type>  -> pybind11_type
  AttributeUtils<no signature: pybind11_type>  -> pybind11_type
  BasePattern<no signature: pybind11_type>  -> pybind11_type
  BaseType<no signature: pybind11_type>  -> pybind11_type
  BaseTypeRegistry<no signature: pybind11_type>  -> pybind11_type
  BatchWorkItem<no signature: pybind11_type>  -> pybind11_type
  Command<no signature: pybind11_type>  -> pybind11_type
  CommandChunk<no signature: pybind11_type>  -> pybind11_type
  ConnectResult<no signature: pybind11_type>  -> pybind11_type
  ConstWorkItemList<no signature: pybind11_type>  -> pybind11_type
  CookError<no signature: type>  -> type
  CookOptions<no signature: pybind11_type>  -> pybind11_type
  DeferredTask<no signature: pybind11_type>  -> pybind11_type
  DeleteResult<no signature: pybind11_type>  -> pybind11_type
  Dependency<no signature: pybind11_type>  -> pybind11_type
  DependencyHolder<no signature: pybind11_type>  -> pybind11_type
  DependencyType<no signature: pybind11_type>  -> pybind11_type
  Dictionary<no signature: pybind11_type>  -> pybind11_type
  DisconnectResult<no signature: pybind11_type>  -> pybind11_type
  EvaluationContext<no signature: pybind11_type>  -> pybind11_type
  EvaluationOptions<no signature: pybind11_type>  -> pybind11_type
  Event<no signature: pybind11_type>  -> pybind11_type
  EventEmitter<no signature: pybind11_type>  -> pybind11_type
  EventHandler<no signature: pybind11_type>  -> pybind11_type
  EventType<no signature: pybind11_type>  -> pybind11_type
  ExpressionError<no signature: type>  -> type
  FeedbackBegin<no signature: pybind11_type>  -> pybind11_type
  File<no signature: pybind11_type>  -> pybind11_type
  FileDependency<no signature: pybind11_type>  -> pybind11_type
  Filter<no signature: pybind11_type>  -> pybind11_type
  FilterPattern<no signature: pybind11_type>  -> pybind11_type
  FrameUtils<no signature: pybind11_type>  -> pybind11_type
  Graph<no signature: pybind11_type>  -> pybind11_type
  GraphContext<no signature: pybind11_type>  -> pybind11_type
  IgnoreAttributeWarningsBlock<no signature: pybind11_type>  -> pybind11_type
  InjectBlock<no signature: pybind11_type>  -> pybind11_type
  JobScriptInfo<no signature: pybind11_type>  -> pybind11_type
  LockAttributesBlock<no signature: pybind11_type>  -> pybind11_type
  Mapper<no signature: pybind11_type>  -> pybind11_type
  MemoryInfo<no signature: pybind11_type>  -> pybind11_type
  Node<no signature: pybind11_type>  -> pybind11_type
  NodeCallbackType<no signature: pybind11_type>  -> pybind11_type
  NodeInterface<no signature: pybind11_type>  -> pybind11_type
  NodeOptions<no signature: pybind11_type>  -> pybind11_type
  NodeStats<no signature: pybind11_type>  -> pybind11_type
  PartitionHolder<no signature: pybind11_type>  -> pybind11_type
  Partitioner<no signature: pybind11_type>  -> pybind11_type
  PathMap<no signature: pybind11_type>  -> pybind11_type
  PathMapEditBlock<no signature: pybind11_type>  -> pybind11_type
  PathMapEntry<no signature: pybind11_type>  -> pybind11_type
  Port<no signature: pybind11_type>  -> pybind11_type
  Processor<no signature: pybind11_type>  -> pybind11_type
  PyBaseObject<no signature: pybind11_type>  -> pybind11_type
  PyDeferredTask<no signature: pybind11_type>  -> pybind11_type
  PyDependency(dependency, key)  -> type
  PyDependencyType<no signature: pybind11_type>  -> pybind11_type
  PyEventHandler<no signature: pybind11_type>  -> pybind11_type
  PyMapper(node)  -> type
  PyNodeCallbackType<no signature: pybind11_type>  -> pybind11_type
  PyPartitioner(node)  -> type
  PyProcessor(node)  -> type
  PyScheduler(scheduler, name)  -> type
  PySchedulerType<no signature: pybind11_type>  -> pybind11_type
  PyWorkItem(item)  -> type
  PyWorkItemData<no signature: pybind11_type>  -> pybind11_type
  PyWorkItemDataType<no signature: pybind11_type>  -> pybind11_type
  RemoveDependencyResult<no signature: pybind11_type>  -> pybind11_type
  RenameNodeResult<no signature: pybind11_type>  -> pybind11_type
  Scheduler<no signature: pybind11_type>  -> pybind11_type
  SchedulerBase<no signature: pybind11_type>  -> pybind11_type
  SchedulerType<no signature: pybind11_type>  -> pybind11_type
  ScriptWorkItemData<no signature: pybind11_type>  -> pybind11_type
  SearchType()  -> type
  Service<no signature: pybind11_type>  -> pybind11_type
  ServiceAddClientsBlock<no signature: pybind11_type>  -> pybind11_type
  ServiceClientInfo<no signature: pybind11_type>  -> pybind11_type
  ServiceClientLogType<no signature: pybind11_type>  -> pybind11_type
  ServiceError<no signature: type>  -> type
  ServiceManager<no signature: pybind11_type>  -> pybind11_type
  ServiceType<no signature: pybind11_type>  -> pybind11_type
  SetDefaultSchedulerResult<no signature: pybind11_type>  -> pybind11_type
  SetExpressionResult<no signature: pybind11_type>  -> pybind11_type
  SetSchedulerResult<no signature: pybind11_type>  -> pybind11_type
  SetValueResult<no signature: pybind11_type>  -> pybind11_type
  TransferPair<no signature: pybind11_type>  -> pybind11_type
  TypeInstance<no signature: pybind11_type>  -> pybind11_type
  TypeRegistry<no signature: pybind11_type>  -> pybind11_type
  ValuePattern<no signature: pybind11_type>  -> pybind11_type
  WorkItem<no signature: pybind11_type>  -> pybind11_type
  WorkItemData<no signature: pybind11_type>  -> pybind11_type
  WorkItemDataType<no signature: pybind11_type>  -> pybind11_type
  WorkItemDirty<no signature: pybind11_type>  -> pybind11_type
  WorkItemHolder<no signature: pybind11_type>  -> pybind11_type
  WorkItemList<no signature: pybind11_type>  -> pybind11_type
  WorkItemOptions<no signature: pybind11_type>  -> pybind11_type
  WorkItemStats<no signature: pybind11_type>  -> pybind11_type
  acceptResult<no signature: pybind11_type>  -> pybind11_type
  argType<no signature: pybind11_type>  -> pybind11_type
  attrgetter<no signature: type>  -> type
  attrib(name, index=None, default_value=None)  -> function
  attribCollisionStrategy<no signature: pybind11_type>  -> pybind11_type
  attribCopyType<no signature: pybind11_type>  -> pybind11_type
  attribErrorLevel<no signature: pybind11_type>  -> pybind11_type
  attribFlag<no signature: pybind11_type>  -> pybind11_type
  attribMatchType<no signature: pybind11_type>  -> pybind11_type
  attribMergeType<no signature: pybind11_type>  -> pybind11_type
  attribOrigin<no signature: pybind11_type>  -> pybind11_type
  attribOverwrite<no signature: pybind11_type>  -> pybind11_type
  attribSaveType<no signature: pybind11_type>  -> pybind11_type
  attribType<no signature: pybind11_type>  -> pybind11_type
  batchActivation<no signature: pybind11_type>  -> pybind11_type
  cacheMode<no signature: pybind11_type>  -> pybind11_type
  cacheModeMenu()  -> function
  cacheResult<no signature: pybind11_type>  -> pybind11_type
  callback = <module 'pdg.callback'>  -> module
  cloneMode<no signature: pybind11_type>  -> pybind11_type
  collectDirectResultData(item, tag, localized=False)  -> function
  context = <module 'pdg.context'>  -> module
  cookType<no signature: pybind11_type>  -> pybind11_type
  dataType<no signature: pybind11_type>  -> pybind11_type
  debugLevelCache<no signature: pybind11_type>  -> pybind11_type
  debugLevelExpression<no signature: pybind11_type>  -> pybind11_type
  debugLevelNode<no signature: pybind11_type>  -> pybind11_type
  debugLevelScheduler<no signature: pybind11_type>  -> pybind11_type
  debugLevelService<no signature: pybind11_type>  -> pybind11_type
  debugLevelTransfer<no signature: pybind11_type>  -> pybind11_type
  debugLevelTypeRegistration<no signature: pybind11_type>  -> pybind11_type
  debugLevelWorkItem<no signature: pybind11_type>  -> pybind11_type
  debugLogType<no signature: pybind11_type>  -> pybind11_type
  debugging<no signature: pybind11_type>  -> pybind11_type
  defaultErrorHandler(event)  -> function
  dependency = <module 'pdg.dependency'>  -> module
  deque<no signature: type>  -> type
  dirtyHandlerType<no signature: pybind11_type>  -> pybind11_type
  envVar(item, var)  -> function
  feedback = <module 'pdg.feedback'>  -> module
  fileTransferType<no signature: pybind11_type>  -> pybind11_type
  fileType<no signature: pybind11_type>  -> pybind11_type
  findData(item, name)  -> function
  findDirectData(item, name)  -> function
  findDirectResultData(item, tag, localized=False, as_list=False)  -> function
  findResultData(item, tag, localized=False, as_list=False)  -> function
  find_first_of(item_list, pred, stop_at_partition)  -> function
  floatData(item, field, index=0)  -> function
  floatDataArray(item, field)  -> function
  generateWhen<no signature: pybind11_type>  -> pybind11_type
  generateWhenMenu()  -> function
  generationType<no signature: pybind11_type>  -> pybind11_type
  genericGeneratorPresets()  -> function
  hasFloatData(item, field, index=0)  -> function
  hasIntData(item, field, index=0)  -> function
  hasResultData(item, tag)  -> function
  hasStrData(item, field, index=0)  -> function
  input(index=None, tag=None, localize=False)  -> function
  intData(item, field, index=0)  -> function
  intDataArray(item, field)  -> function
  isEvaluating()  -> function
  isIterable(obj)  -> function
  job = <module 'pdg.job'>  -> module
  kwargs(arg=None)  -> function
  language<no signature: pybind11_type>  -> pybind11_type
  logger = <Logger pdg (WARNING)>  -> Logger
  logging = <module 'logging'>  -> module
  mapper = <module 'pdg.mapper'>  -> module
  mergeOperationMenu()  -> function
  node = <module 'pdg.node'>  -> module
  nodeStatType<no signature: pybind11_type>  -> pybind11_type
  nodeSubtype<no signature: pybind11_type>  -> pybind11_type
  nodeType<no signature: pybind11_type>  -> pybind11_type
  os = <module 'os' (frozen)>  -> module
  parms = <module 'pdg.parms'>  -> module
  partitioner = <module 'pdg.partitioner'>  -> module
  pathMapMatchType<no signature: pybind11_type>  -> pybind11_type
  platform<no signature: pybind11_type>  -> pybind11_type
  portType<no signature: pybind11_type>  -> pybind11_type
  processor = <module 'pdg.processor'>  -> module
  regenerateReason<no signature: pybind11_type>  -> pybind11_type
  regenerateResult<no signature: pybind11_type>  -> pybind11_type
  registeredType<no signature: pybind11_type>  -> pybind11_type
  result<no signature: pybind11_type>  -> pybind11_type
  resultData(item, tag, localized=False, as_list=False)  -> function
  resultDataIndex(item, tag, index, default='', localized=False)  -> function
  resultTagMenu(prefix)  -> function
  scheduleResult<no signature: pybind11_type>  -> pybind11_type
  scheduler = <module 'pdg.scheduler'>  -> module
  serviceBlockCookType<no signature: pybind11_type>  -> pybind11_type
  serviceClientLogType<no signature: pybind11_type>  -> pybind11_type
  serviceOwner<no signature: pybind11_type>  -> pybind11_type
  serviceResetType<no signature: pybind11_type>  -> pybind11_type
  serviceState<no signature: pybind11_type>  -> pybind11_type
  staticcook = <module 'pdg.staticcook'>  -> module
  strData(item, field, index=0)  -> function
  strDataArray(item, field)  -> function
  tickResult<no signature: pybind11_type>  -> pybind11_type
  time = <module 'time' (built-in)>  -> module
  toplevel = <module 'pdg.toplevel'>  -> module
  transferResult<no signature: pybind11_type>  -> pybind11_type
  types = <module 'pdg.types'>  -> module
  utils = <module 'pdg.utils'>  -> module
  workItem()  -> function
  workItemCacheState<no signature: pybind11_type>  -> pybind11_type
  workItemCookType<no signature: pybind11_type>  -> pybind11_type
  workItemDataSource<no signature: pybind11_type>  -> pybind11_type
  workItemDirtyType<no signature: pybind11_type>  -> pybind11_type
  workItemExecutionType<no signature: pybind11_type>  -> pybind11_type
  workItemLogType<no signature: pybind11_type>  -> pybind11_type
  workItemReadyResult<no signature: pybind11_type>  -> pybind11_type
  workItemStatType<no signature: pybind11_type>  -> pybind11_type
  workItemState<no signature: pybind11_type>  -> pybind11_type
  workItemType<no signature: pybind11_type>  -> pybind11_type
  workitem = <module 'pdg.workitem'>  -> module
```

### 2.3 Scheduler surfaces — `hou.pdg.scheduler`, `pdg.Scheduler`, `pdg.SchedulerType`

#### `hou.pdg.scheduler`
**STATUS:** NOT RESOLVABLE — ``hou.pdg.scheduler`` does not exist.

#### `pdg.Scheduler`
**STATUS:** RESOLVED · **Type:** ``pybind11_type`` · **Repr:** ``<class '_pdg.Scheduler'>``

**__doc__:** *Python binding for schedulers created in Python*

**dir() — 103 attributes:**
```
  __iter__<no signature: instancemethod>  -> instancemethod
  addEventHandler<no signature: instancemethod>  -> instancemethod
  applicationBin<no signature: instancemethod>  -> instancemethod
  attributeInfo = <property>  -> property
  cleanTempDirectory<no signature: instancemethod>  -> instancemethod
  clearSharedServerInfo<no signature: instancemethod>  -> instancemethod
  commonVars = <property>  -> property
  context = <property>  -> property
  cookError<no signature: instancemethod>  -> instancemethod
  cookWarning<no signature: instancemethod>  -> instancemethod
  cookWorkItem<no signature: instancemethod>  -> instancemethod
  customId = <property>  -> property
  customParameters = <property>  -> property
  dataDir<no signature: instancemethod>  -> instancemethod
  default<no signature: instancemethod>  -> instancemethod
  delocalizePath<no signature: instancemethod>  -> instancemethod
  dependencyGraph<no signature: instancemethod>  -> instancemethod
  endSharedServer<no signature: instancemethod>  -> instancemethod
  evaluateBoolOverride<no signature: instancemethod>  -> instancemethod
  evaluateFloatOverride<no signature: instancemethod>  -> instancemethod
  evaluateIntOverride<no signature: instancemethod>  -> instancemethod
  evaluateStringOverride<no signature: instancemethod>  -> instancemethod
  eventHandlers = <property>  -> property
  expandCommandTokens<no signature: instancemethod>  -> instancemethod
  formatTransferPath<no signature: instancemethod>  -> instancemethod
  getDefaultUserEnvironment<no signature: builtin_function_or_method>  -> builtin
  getLogURI<no signature: instancemethod>  -> instancemethod
  getPollingClient<no signature: instancemethod>  -> instancemethod
  getSharedServerInfo<no signature: instancemethod>  -> instancemethod
  getSharedServers<no signature: instancemethod>  -> instancemethod
  getStatusURI<no signature: instancemethod>  -> instancemethod
  hasEventHandler<no signature: instancemethod>  -> instancemethod
  input<no signature: instancemethod>  -> instancemethod
  inputCount = <property>  -> property
  inputNames = <property>  -> property
  inputs = <property>  -> property
  inputsForNode<no signature: instancemethod>  -> instancemethod
  inputsForWorkItem<no signature: instancemethod>  -> instancemethod
  isCompressWorkItemData = <property>  -> property
  isItemFromPort<no signature: instancemethod>  -> instancemethod
  isWaitForFailures = <property>  -> property
  isWorkItemReady<no signature: instancemethod>  -> instancemethod
  jobName<no signature: instancemethod>  -> instancemethod
  localizePath<no signature: instancemethod>  -> instancemethod
  logDir<no signature: instancemethod>  -> instancemethod
  maxThreads<no signature: builtin_function_or_method>  -> builtin
  name = <property>  -> property
  onWorkItemAddOutput<no signature: instancemethod>  -> instancemethod
  onWorkItemAddOutputs<no signature: instancemethod>  -> instancemethod
  onWorkItemAppendLog<no signature: instancemethod>  -> instancemethod
  onWorkItemCanceled<no signature: instancemethod>  -> instancemethod
  onWorkItemFailed<no signature: instancemethod>  -> instancemethod
  onWorkItemFileResult<no signature: instancemethod>  -> instancemethod
  onWorkItemInvalidateCache<no signature: instancemethod>  -> instancemethod
  onWorkItemSetAttribute<no signature: instancemethod>  -> instancemethod
  onWorkItemSetCookPercent<no signature: instancemethod>  -> instancemethod
  onWorkItemSetCustomState<no signature: instancemethod>  -> instancemethod
  onWorkItemSetDictAttrib<no signature: instancemethod>  -> instancemethod
  onWorkItemSetFileAttrib<no signature: instancemethod>  -> instancemethod
  onWorkItemSetFloatAttrib<no signature: instancemethod>  -> instancemethod
  onWorkItemSetIntAttrib<no signature: instancemethod>  -> instancemethod
  onWorkItemSetPyObjectAttrib<no signature: instancemethod>  -> instancemethod
  onWorkItemSetStringAttrib<no signature: instancemethod>  -> instancemethod
  onWorkItemStartCook<no signature: instancemethod>  -> instancemethod
  onWorkItemSucceeded<no signature: instancemethod>  -> instancemethod
  output<no signature: instancemethod>  -> instancemethod
  outputCount = <property>  -> property
  outputNames = <property>  -> property
  outputs = <property>  -> property
  parameter<no signature: instancemethod>  -> instancemethod
  parameterCount = <property>  -> property
  parameterNames = <property>  -> property
  parameters = <property>  -> property
  parametersForTag<no signature: instancemethod>  -> instancemethod
  port<no signature: instancemethod>  -> instancemethod
  portCount<no signature: instancemethod>  -> instancemethod
  ports<no signature: instancemethod>  -> instancemethod
  postExecProcess<no signature: builtin_function_or_method>  -> builtin
  preExecProcess<no signature: builtin_function_or_method>  -> builtin
  removeAllEventHandlers<no signature: instancemethod>  -> instancemethod
  removeEventHandler<no signature: instancemethod>  -> instancemethod
  runOnMainThread(self, wait, function, *args, **kwargs)  -> function
  scriptDir<no signature: instancemethod>  -> instancemethod
  scriptInfo = <property>  -> property
  setAcceptInProcess<no signature: instancemethod>  -> instancemethod
  setScriptDir<no signature: instancemethod>  -> instancemethod
  setSharedServerInfo<no signature: instancemethod>  -> instancemethod
  setTempDir<no signature: instancemethod>  -> instancemethod
  setWorkingDir<no signature: instancemethod>  -> instancemethod
  startService<no signature: instancemethod>  -> instancemethod
  stopService<no signature: instancemethod>  -> instancemethod
  submitAsJob<no signature: instancemethod>  -> instancemethod
  supportedEventTypes = <property>  -> property
  tempDir<no signature: instancemethod>  -> instancemethod
  templateName = <property>  -> property
  topNode(self)  -> function
  topNodeId = <property>  -> property
  transferFile<no signature: instancemethod>  -> instancemethod
  type = <property>  -> property
  typeName = <property>  -> property
  value<no signature: instancemethod>  -> instancemethod
  workItemDataSource = <property>  -> property
  workingDir<no signature: instancemethod>  -> instancemethod
```

#### `pdg.SchedulerType`
**STATUS:** RESOLVED · **Type:** ``pybind11_type`` · **Repr:** ``<class '_pdg.SchedulerType'>``

**dir() — 6 attributes:**
```
  instanceCount = <property>  -> property
  instanceMemoryUsage = <property>  -> property
  language = <property>  -> property
  parm_category = <property>  -> property
  typeLabel = <property>  -> property
  typeName = <property>  -> property
```

### 2.4 WorkItem surfaces — `hou.pdg.workItem`, `pdg.WorkItem`

#### `hou.pdg.workItem`
**STATUS:** NOT RESOLVABLE — ``hou.pdg.workItem`` does not exist.

#### `pdg.WorkItem`
**STATUS:** RESOLVED · **Type:** ``pybind11_type`` · **Repr:** ``<class '_pdg.WorkItem'>``

**__doc__:** *Python bindings for PDG work item base class.*

**dir() — 173 attributes:**
```
  Serialization<no signature: pybind11_type>  -> pybind11_type
  __iter__<no signature: instancemethod>  -> instancemethod
  addAttrib<no signature: instancemethod>  -> instancemethod
  addEnvironmentVar<no signature: instancemethod>  -> instancemethod
  addError<no signature: instancemethod>  -> instancemethod
  addEventHandler<no signature: instancemethod>  -> instancemethod
  addExpectedOutputFile<no signature: instancemethod>  -> instancemethod
  addExpectedOutputFiles<no signature: instancemethod>  -> instancemethod
  addExpectedResultData<no signature: instancemethod>  -> instancemethod
  addLog<no signature: instancemethod>  -> instancemethod
  addMessage<no signature: instancemethod>  -> instancemethod
  addOutputFile<no signature: instancemethod>  -> instancemethod
  addOutputFiles<no signature: instancemethod>  -> instancemethod
  addResultData<no signature: instancemethod>  -> instancemethod
  addWarning<no signature: instancemethod>  -> instancemethod
  attrib<no signature: instancemethod>  -> instancemethod
  attribArray<no signature: instancemethod>  -> instancemethod
  attribHash<no signature: instancemethod>  -> instancemethod
  attribMatch<no signature: instancemethod>  -> instancemethod
  attribNames<no signature: instancemethod>  -> instancemethod
  attribType<no signature: instancemethod>  -> instancemethod
  attribValue<no signature: instancemethod>  -> instancemethod
  attribValues<no signature: instancemethod>  -> instancemethod
  batchIndex = <property>  -> property
  batchParent = <property>  -> property
  cancel<no signature: instancemethod>  -> instancemethod
  checkSubItem<no signature: instancemethod>  -> instancemethod
  clearAttribs<no signature: instancemethod>  -> instancemethod
  clearEnvironment<no signature: instancemethod>  -> instancemethod
  clearExpectedOutputFiles<no signature: instancemethod>  -> instancemethod
  clearExpectedOutputs<no signature: instancemethod>  -> instancemethod
  clearOutputFiles<no signature: instancemethod>  -> instancemethod
  clearResultData<no signature: instancemethod>  -> instancemethod
  command = <property>  -> property
  context = <property>  -> property
  cookDuration = <property>  -> property
  cookPercent = <property>  -> property
  cookSubItem<no signature: instancemethod>  -> instancemethod
  cookType = <property>  -> property
  cookWarning<no signature: instancemethod>  -> instancemethod
  createJSONPatch<no signature: instancemethod>  -> instancemethod
  customState = <property>  -> property
  data = <property>  -> property
  dependencies = <property>  -> property
  dependencyState = <property>  -> property
  dependents = <property>  -> property
  dictAttribArray<no signature: instancemethod>  -> instancemethod
  dictAttribValue<no signature: instancemethod>  -> instancemethod
  dirty<no signature: instancemethod>  -> instancemethod
  envLookup<no signature: instancemethod>  -> instancemethod
  environment = <property>  -> property
  eraseAttrib<no signature: instancemethod>  -> instancemethod
  eventHandlers = <property>  -> property
  executionType = <property>  -> property
  expectedInputFiles = <property>  -> property
  expectedInputResultData = <property>  -> property
  expectedOutputFiles = <property>  -> property
  expectedResultData = <property>  -> property
  failedDependencies = <property>  -> property
  fileAttribArray<no signature: instancemethod>  -> instancemethod
  fileAttribValue<no signature: instancemethod>  -> instancemethod
  firstOutputFileForTag<no signature: instancemethod>  -> instancemethod
  firstResultDataForTag<no signature: instancemethod>  -> instancemethod
  floatAttribArray<no signature: instancemethod>  -> instancemethod
  floatAttribValue<no signature: instancemethod>  -> instancemethod
  frame = <property>  -> property
  frameStep = <property>  -> property
  graph = <property>  -> property
  hasAttrib<no signature: instancemethod>  -> instancemethod
  hasCommand = <property>  -> property
  hasCookPercent = <property>  -> property
  hasCustomState = <property>  -> property
  hasDependency<no signature: instancemethod>  -> instancemethod
  hasEnvironmentVar<no signature: instancemethod>  -> instancemethod
  hasEventHandler<no signature: instancemethod>  -> instancemethod
  hasFrame = <property>  -> property
  hasLabel = <property>  -> property
  hasPlatformCommand = <property>  -> property
  hasWarnings = <property>  -> property
  id = <property>  -> property
  index = <property>  -> property
  inputFiles = <property>  -> property
  inputFilesForTag<no signature: instancemethod>  -> instancemethod
  inputResultData = <property>  -> property
  inputResultDataForTag<no signature: instancemethod>  -> instancemethod
  intAttribArray<no signature: instancemethod>  -> instancemethod
  intAttribValue<no signature: instancemethod>  -> instancemethod
  invalidateCache<no signature: instancemethod>  -> instancemethod
  isBatch = <property>  -> property
  isCooked = <property>  -> property
  isFrozen = <property>  -> property
  isInProcess = <property>  -> property
  isNoGenerate = <property>  -> property
  isOutOfProcess = <property>  -> property
  isPartition = <property>  -> property
  isPostCook = <property>  -> property
  isStatic = <property>  -> property
  isSuccessful = <property>  -> property
  isUnsuccessful = <property>  -> property
  label = <property>  -> property
  loadAttributes<no signature: instancemethod>  -> instancemethod
  loadJSONFile<no signature: builtin_function_or_method>  -> builtin
  loadJSONString<no signature: builtin_function_or_method>  -> builtin
  localizePath<no signature: instancemethod>  -> instancemethod
  lockAttributes<no signature: instancemethod>  -> instancemethod
  logMessages = <property>  -> property
  logURI = <property>  -> property
  loopBegin<no signature: instancemethod>  -> instancemethod
  loopDepth = <property>  -> property
  loopIteration = <property>  -> property
  loopLock = <property>  -> property
  loopNumber = <property>  -> property
  loopSize = <property>  -> property
  makeActive<no signature: instancemethod>  -> instancemethod
  memoryUsage<no signature: instancemethod>  -> instancemethod
  name = <property>  -> property
  node = <property>  -> property
  numAttribs<no signature: instancemethod>  -> instancemethod
  numericAttribute<no signature: instancemethod>  -> instancemethod
  outputCacheState = <property>  -> property
  outputFiles = <property>  -> property
  outputFilesForTag<no signature: instancemethod>  -> instancemethod
  parent = <property>  -> property
  partitionItems = <property>  -> property
  platformCommand<no signature: instancemethod>  -> instancemethod
  prepareDirty<no signature: instancemethod>  -> instancemethod
  priority = <property>  -> property
  pyObjectAttribValue<no signature: instancemethod>  -> instancemethod
  removeAllEventHandlers<no signature: instancemethod>  -> instancemethod
  removeEventHandler<no signature: instancemethod>  -> instancemethod
  renameAttrib<no signature: instancemethod>  -> instancemethod
  resultData = <property>  -> property
  resultDataForTag<no signature: instancemethod>  -> instancemethod
  saveArrayDict<no signature: builtin_function_or_method>  -> builtin
  saveArrayJSONFile<no signature: builtin_function_or_method>  -> builtin
  saveArrayJSONString<no signature: builtin_function_or_method>  -> builtin
  saveAttributes<no signature: instancemethod>  -> instancemethod
  saveDict<no signature: instancemethod>  -> instancemethod
  saveJSONFile<no signature: instancemethod>  -> instancemethod
  saveJSONString<no signature: instancemethod>  -> instancemethod
  savePythonDict<no signature: instancemethod>  -> instancemethod
  serializeData<no signature: instancemethod>  -> instancemethod
  serializeDataToFile<no signature: instancemethod>  -> instancemethod
  setAttribFlag<no signature: instancemethod>  -> instancemethod
  setCommand<no signature: instancemethod>  -> instancemethod
  setCookPercent<no signature: instancemethod>  -> instancemethod
  setCustomState<no signature: instancemethod>  -> instancemethod
  setDictAttrib<no signature: instancemethod>  -> instancemethod
  setFileAttrib<no signature: instancemethod>  -> instancemethod
  setFloatAttrib<no signature: instancemethod>  -> instancemethod
  setFrame<no signature: instancemethod>  -> instancemethod
  setIntAttrib<no signature: instancemethod>  -> instancemethod
  setIsPostCook<no signature: instancemethod>  -> instancemethod
  setLabel<no signature: instancemethod>  -> instancemethod
  setLoopInfo<no signature: instancemethod>  -> instancemethod
  setPlatformCommands<no signature: instancemethod>  -> instancemethod
  setPyObjectAttrib<no signature: instancemethod>  -> instancemethod
  setStringAttrib<no signature: instancemethod>  -> instancemethod
  shouldRunInShell = <property>  -> property
  startSubItem<no signature: instancemethod>  -> instancemethod
  state = <property>  -> property
  stats<no signature: instancemethod>  -> instancemethod
  statusURI = <property>  -> property
  stringAttribArray<no signature: instancemethod>  -> instancemethod
  stringAttribValue<no signature: instancemethod>  -> instancemethod
  stringAttribute<no signature: instancemethod>  -> instancemethod
  supportedEventTypes = <property>  -> property
  tempDir = <property>  -> property
  timeDependentAttribs<no signature: instancemethod>  -> instancemethod
  transferFiles<no signature: instancemethod>  -> instancemethod
  type = <property>  -> property
  updateOutputFile<no signature: instancemethod>  -> instancemethod
  updateResultData<no signature: instancemethod>  -> instancemethod
```

### 2.5 Event subscription API

#### `pdg.PyEventHandler`
**STATUS:** RESOLVED · **Type:** ``pybind11_type`` · **Repr:** ``<class '_pdg.PyEventHandler'>``

**__doc__:** *Python bindings for event handler object*

**dir() — 4 attributes:**
```
  callback = <property>  -> property
  emitters = <property>  -> property
  language = <property>  -> property
  removeFromAllEmitters<no signature: instancemethod>  -> instancemethod
```

#### `pdg.EventType` (enum)
**STATUS:** RESOLVED · **Type:** ``pybind11_type``

**Members (public, value-bearing):**
```
  All = <EventType.All: 43>
  CookComplete = <EventType.CookComplete: 14>
  CookError = <EventType.CookError: 12>
  CookStart = <EventType.CookStart: 38>
  CookWarning = <EventType.CookWarning: 13>
  DirtyAll = <EventType.DirtyAll: 17>
  DirtyStart = <EventType.DirtyStart: 15>
  DirtyStop = <EventType.DirtyStop: 16>
  Log = <EventType.Log: 44>
  NodeClear = <EventType.NodeClear: 11>
  NodeConnect = <EventType.NodeConnect: 22>
  NodeCooked = <EventType.NodeCooked: 26>
  NodeCreate = <EventType.NodeCreate: 19>
  NodeDisconnect = <EventType.NodeDisconnect: 23>
  NodeFirstCook = <EventType.NodeFirstCook: 24>
  NodeGenerated = <EventType.NodeGenerated: 25>
  NodeProgressUpdate = <EventType.NodeProgressUpdate: 41>
  NodeRemove = <EventType.NodeRemove: 20>
  NodeRename = <EventType.NodeRename: 21>
  NodeSetScheduler = <EventType.NodeSetScheduler: 47>
  Null = <EventType.Null: 0>
  SchedulerAdded = <EventType.SchedulerAdded: 45>
  SchedulerRemoved = <EventType.SchedulerRemoved: 46>
  ServiceClientChanged = <EventType.ServiceClientChanged: 52>
  ServiceClientStarted = <EventType.ServiceClientStarted: 51>
  ServiceManagerAll = <EventType.ServiceManagerAll: 48>
  ServiceStartBegin = <EventType.ServiceStartBegin: 49>
  ServiceStartEnd = <EventType.ServiceStartEnd: 50>
  UISelect = <EventType.UISelect: 18>
  WorkItemAdd = <EventType.WorkItemAdd: 1>
  WorkItemAddDep = <EventType.WorkItemAddDep: 7>
  WorkItemAddList = <EventType.WorkItemAddList: 2>
  WorkItemAddParent = <EventType.WorkItemAddParent: 9>
  WorkItemAddStaticAncestor = <EventType.WorkItemAddStaticAncestor: 39>
  WorkItemCookPercentUpdate = <EventType.WorkItemCookPercentUpdate: 6>
  WorkItemFrame = <EventType.WorkItemFrame: 37>
  WorkItemMerge = <EventType.WorkItemMerge: 34>
  WorkItemOutputFiles = <EventType.WorkItemResult: 35>
  WorkItemPriority = <EventType.WorkItemPriority: 36>
  WorkItemRemove = <EventType.WorkItemRemove: 3>
  WorkItemRemoveDep = <EventType.WorkItemRemoveDep: 8>
  WorkItemRemoveList = <EventType.WorkItemRemoveList: 4>
  WorkItemRemoveParent = <EventType.WorkItemRemoveParent: 10>
  WorkItemRemoveStaticAncestor = <EventType.WorkItemRemoveStaticAncestor: 40>
  WorkItemResult = <EventType.WorkItemResult: 35>
  WorkItemSetDict = <EventType.WorkItemSetDict: 31>
  WorkItemSetFile = <EventType.WorkItemSetFile: 30>
  WorkItemSetFloat = <EventType.WorkItemSetFloat: 28>
  WorkItemSetGeometry = <EventType.WorkItemSetGeometry: 33>
  WorkItemSetInt = <EventType.WorkItemSetInt: 27>
  WorkItemSetPyObject = <EventType.WorkItemSetPyObject: 32>
  WorkItemSetString = <EventType.WorkItemSetString: 29>
  WorkItemStateChange = <EventType.WorkItemStateChange: 5>
```

#### `pdg.EventHandler` (abstract base)
**STATUS:** RESOLVED · **Type:** ``pybind11_type`` · **Repr:** ``<class '_pdg.EventHandler'>``

**dir() — 3 attributes:**
```
  emitters = <property>  -> property
  language = <property>  -> property
  removeFromAllEmitters<no signature: instancemethod>  -> instancemethod
```

#### `pdg.PyEventCallback` (alt name)
**STATUS:** NOT RESOLVABLE — ``pdg.PyEventCallback`` does not exist. The correct class name is ``pdg.PyEventHandler`` above.

### 2.6 Callback registration shape

#### `pdg.GraphContext`
**STATUS:** RESOLVED · **Type:** ``pybind11_type`` · **Repr:** ``<class '_pdg.GraphContext'>``

**__doc__:** *Python binding for PDG Graph Context. Can be constructed in Python to create a new pdg.Graph*

**dir() — 68 attributes:**
```
  addDependency(self, type_name, node_name, key, *args, **kwargs)  -> function
  addEventHandler<no signature: instancemethod>  -> instancemethod
  addFileDependency(self, node_name, file_name)  -> function
  addNode(self, type_name, name='', *args, **kwargs)  -> function
  addParameter<no signature: instancemethod>  -> instancemethod
  addScheduler(self, type_name, name='', *args, **kwargs)  -> function
  addWorkItem<no signature: instancemethod>  -> instancemethod
  addWorkItemDependency<no signature: instancemethod>  -> instancemethod
  addWorkItemPropagateDep<no signature: instancemethod>  -> instancemethod
  addWorkItemResults<no signature: instancemethod>  -> instancemethod
  beginDeserialization<no signature: instancemethod>  -> instancemethod
  byName<no signature: builtin_function_or_method>  -> builtin
  cancelCook<no signature: instancemethod>  -> instancemethod
  canceling = <property>  -> property
  chunkDepth = <property>  -> property
  cleanTempDirectory<no signature: instancemethod>  -> instancemethod
  commandDescriptions = <property>  -> property
  commitChunk<no signature: instancemethod>  -> instancemethod
  commitWorkItem<no signature: instancemethod>  -> instancemethod
  connect<no signature: instancemethod>  -> instancemethod
  cook<no signature: instancemethod>  -> instancemethod
  cookItems<no signature: instancemethod>  -> instancemethod
  cookOptions = <property>  -> property
  cookSet = <property>  -> property
  cooking = <property>  -> property
  defaultScheduler = <property>  -> property
  delete<no signature: instancemethod>  -> instancemethod
  deserializeWorkItemFromJSON<no signature: instancemethod>  -> instancemethod
  deserializeWorkItems(self, filepath)  -> function
  disconnect<no signature: instancemethod>  -> instancemethod
  eventHandlers = <property>  -> property
  findFile<no signature: builtin_function_or_method>  -> builtin
  getSharedServerInfo<no signature: instancemethod>  -> instancemethod
  globFiles<no signature: builtin_function_or_method>  -> builtin
  globTypeFiles<no signature: builtin_function_or_method>  -> builtin
  graph = <property>  -> property
  hasEventHandler<no signature: instancemethod>  -> instancemethod
  memoryUsage<no signature: instancemethod>  -> instancemethod
  name = <property>  -> property
  names<no signature: builtin_function_or_method>  -> builtin
  openChunk<no signature: instancemethod>  -> instancemethod
  pauseCook<no signature: instancemethod>  -> instancemethod
  redo<no signature: instancemethod>  -> instancemethod
  removeAllEventHandlers<no signature: instancemethod>  -> instancemethod
  removeDependency<no signature: instancemethod>  -> instancemethod
  removeEventHandler<no signature: instancemethod>  -> instancemethod
  renameNode<no signature: instancemethod>  -> instancemethod
  rollbackChunk<no signature: instancemethod>  -> instancemethod
  saveJSON<no signature: instancemethod>  -> instancemethod
  schedulerForName<no signature: instancemethod>  -> instancemethod
  schedulers = <property>  -> property
  searchPath<no signature: builtin_function_or_method>  -> builtin
  serialize<no signature: instancemethod>  -> instancemethod
  serializeGraph<no signature: instancemethod>  -> instancemethod
  serializeWorkItemToJSON<no signature: instancemethod>  -> instancemethod
  serializeWorkItems<no signature: instancemethod>  -> instancemethod
  setDefaultScheduler<no signature: instancemethod>  -> instancemethod
  setExpression<no signature: instancemethod>  -> instancemethod
  setExpressions(self, name, expressions, **kwargs)  -> function
  setParameter(self, name, param_name, value, index=0, param_type=<argType.Automatic: 0>)  -> function
  setParameters(self, name, parameters, **kwargs)  -> function
  setScheduler<no signature: instancemethod>  -> instancemethod
  setValue(self, node, port, value, index=0)  -> function
  setValues(self, name, values, **kwargs)  -> function
  stateCount = <property>  -> property
  supportedEventTypes = <property>  -> property
  undo<no signature: instancemethod>  -> instancemethod
  waitAllEvents<no signature: instancemethod>  -> instancemethod
```

#### `hou.pdg.GraphContext`
**STATUS:** NOT RESOLVABLE — ``hou.pdg.GraphContext`` does not exist as an importable class path. To get a graph context, use the instance-method on a TOP node: ``top_node.getPDGGraphContext()`` (per ``shared/bridge.py:616`` R8 pattern).

#### `hou.topNodeTypeCategory`
**STATUS:** RESOLVED · **Type:** ``function`` · **Repr:** ``<function topNodeTypeCategory at 0x...>``

**__doc__:**
```
hou.topNodeTypeCategory

Return the NodeTypeCategory instance for Houdini task (top) nodes.

USAGE
  topNodeTypeCategory() -> NodeTypeCategory
```

Sketch's call shape (``hou.topNodeTypeCategory()``) is correct — function, not attribute.

### 2.7 Cook lifecycle event types

Cross-reference: §2.5 ``pdg.EventType`` is the canonical PDG event enum (50+ members covering cook + work-item lifecycle).

#### `hou.nodeEventType` (node-level parallel — non-PDG)
**STATUS:** RESOLVED · **Type:** ``type``

**Members (excerpt — full list captured):**
```
  AppearanceChanged, BeingDeleted, ChildCreated, ChildDeleted,
  ChildReordered, ChildSelectionChanged, ChildSwitched,
  CustomDataChanged, FlagChanged, IndirectInputCreated,
  IndirectInputDeleted, IndirectInputRewired, InputDataChanged,
  InputRewired, NameChanged, NetworkBoxChanged, NetworkBoxCreated,
  NetworkBoxDeleted, ParmTupleAnimated, ParmTupleChanged,
  ParmTupleChannelChanged, ParmTupleEnabledChanged,
  ParmTupleLockChanged, ParmTupleVisibleChanged, PositionChanged,
  SelectionChanged, SpareParmTemplatesChanged, StickyNoteChanged,
  StickyNoteCreated, StickyNoteDeleted, WorkItemSelectionChanged
```

This is the **node-level** event surface (handled by ``hou.OpNode.addEventCallback``). It is **not** the cook-event surface — for cook events, use ``pdg.EventType`` from §2.5.

#### `hou.pdgEventType` (legacy)
**STATUS:** NOT RESOLVABLE — confirms ``shared/bridge.py:568`` doc comment empirically. ``hou.pdgEventType`` was superseded by standalone ``pdg.EventType``.

### 2.8 Auxiliary surfaces

#### `hou.topNodeTypeCategory` (aux probe)
Same surface as §2.6 — confirmed callable; sketch usage is correct.

#### `hou.hipFile`
**STATUS:** RESOLVED · **Type:** ``hipFile`` · **Repr:** ``<module 'hou.hipFile'>``

**dir() — 27 attributes (callback-relevant subset):**
```
  addEventCallback(callback)  -> method
  clearEventCallbacks() -> 'void'  -> function
  eventCallbacks()  -> method
  removeEventCallback(callback)  -> method
  ...plus 23 file-management methods (load, save, basename, etc.)
```

**Critical signature note:** ``addEventCallback(callback)`` takes a callback function and returns ``None``; ``removeEventCallback(callback)`` takes the **same callback function** to remove it. The sketch's ``self._scene_callback_handle = hou.hipFile.addEventCallback(...)`` stores ``None``. Sketch must store the **callback function itself** (e.g. ``self._scene_callback_fn = self._on_hip_event``) and call ``hou.hipFile.removeEventCallback(self._scene_callback_fn)`` for cleanup.

#### `hou.hipFileEventType`
**STATUS:** RESOLVED · **Type:** ``type``

**Members:**
```
  AfterClear, AfterLoad, AfterMerge, AfterSave,
  BeforeClear, BeforeLoad, BeforeMerge, BeforeSave
```

Sketch's ``hou.hipFileEventType.AfterLoad`` reference confirmed correct.

#### `hou.hipFile.addEventCallback` (probe)
**STATUS:** RESOLVED · **Type:** ``method`` · sig: ``addEventCallback(callback)`` — see callback-by-identity note above.

### 2.9 Audit summary

```
Surfaces resolved   : 14
Surfaces missing    : 6
Errors during audit : 0

RESOLVED:
  + pdg
  + pdg.Scheduler
  + pdg.SchedulerType
  + pdg.WorkItem
  + pdg.PyEventHandler
  + pdg.EventType
  + pdg.EventHandler
  + pdg.GraphContext
  + hou.topNodeTypeCategory  (×2 — listed in §2.6 and §2.8)
  + hou.nodeEventType
  + hou.hipFile
  + hou.hipFileEventType
  + hou.hipFile.addEventCallback

MISSING (Spike 3.1 cannot reference these by name):
  - hou.pdg
  - hou.pdg.scheduler
  - hou.pdg.workItem
  - pdg.PyEventCallback
  - hou.pdg.GraphContext
  - hou.pdgEventType
```

---

## 3. Anomalies / surprises / gotchas

**Headline finding:** every ``hou.pdg.*`` path is missing in 21.0.671. The standalone ``pdg`` module is the real PDG surface. ``shared/bridge.py:568+`` already used the correct standalone ``pdg`` module — **the artifact (``CONTINUATION_INSIDE_OUT_TOPS.md``) lagged the codebase**. Spike 3.0 closes that gap; Spike 3.1 designs against ``pdg.*`` from the start.

### 3.1 Watchlist verification

| Hypothesis | Confirmed? | Spike 3.1 impact |
|---|---|---|
| ``hou.pdg`` is thin/empty — real PDG surface lives under standalone ``pdg`` | **Yes — confirmed.** ``hou.pdg`` is not resolvable at all; ``pdg`` exposes 234 attrs including everything the bridge sketch needs | Bridge sketch must rename every ``hou.pdg.*`` reference to ``pdg.*`` |
| ``hou.pdg.GraphContext`` does not resolve — must reach via ``top_node.getPDGGraphContext()`` (R8 pattern, ``bridge.py:616``) | **Yes — confirmed.** ``hou.pdg.GraphContext`` not resolvable. ``pdg.GraphContext`` exists as a class (constructible), but live graph contexts come from ``top_node.getPDGGraphContext()`` instance method | Bridge sketch's class-import path is wrong; instance-method path is correct |
| ``hou.pdgEventType`` does not exist — superseded by ``pdg.EventType`` | **Yes — confirmed.** ``hou.pdgEventType`` not resolvable; ``pdg.EventType`` resolves with 50+ members (CookComplete=14, CookError=12, etc.) | Confirms ``bridge.py:568`` doc comment empirically |
| ``event.workItem.attribValue("frame")`` — ``attribValue`` is the right method name | **Yes — confirmed.** ``pdg.WorkItem.attribValue`` is an instancemethod. ``frame`` also exists as a property — sketch could use either (``frame`` is more direct) | Sketch's ``attribValue("frame")`` works; consider ``.frame`` for clarity |
| ``event.workItem.expectedResultData`` is iterable, each element has ``.path`` | **Partial.** ``expectedResultData`` exists as property on ``pdg.WorkItem``; element shape (``.path`` access) requires runtime example to verify | Flag for runtime verification at first cook in Spike 3.3 |
| ``event.workItem.cookDuration`` exists; unit is seconds (sketch multiplies by 1000) | **Partial.** ``cookDuration`` property exists; unit not in introspectable docstring | Flag for runtime verification — confirm seconds vs ms before shipping ×1000 |
| ``hou.hipFile.addEventCallback`` returns a removable handle | **No — refuted.** Signature is ``addEventCallback(callback)``, returns ``None``. Removal is by callback-identity: ``removeEventCallback(callback)`` takes the **same function** | Sketch's ``self._scene_callback_handle = hou.hipFile.addEventCallback(...)`` is wrong shape — must store the callback function itself |
| ``hou.hipFileEventType.AfterLoad`` spelled exactly that way | **Yes — confirmed.** Member exists, exact spelling | Sketch's ``_on_hip_event`` switch is correct |
| ``hou.topNodeTypeCategory`` is callable (returns category) vs already-a-category attribute | **Yes — confirmed callable.** ``topNodeTypeCategory()`` is a function returning ``NodeTypeCategory`` | Sketch's ``hou.topNodeTypeCategory()`` call is correct |

### 3.2 New findings beyond the watchlist

| Finding | Severity | Spike 3.1 impact |
|---|---|---|
| Both ``pdg.Scheduler`` AND ``pdg.WorkItem`` expose ``addEventHandler`` / ``removeEventHandler`` directly (not just ``pdg.GraphContext``). Per-work-item subscription is a real shape | info | Spike 3.1 may register handlers at scheduler or work-item level, not only graph-context level. Sketch's "register at GraphContext" is one valid path; per-scheduler is another. Decide at design time |
| ``pdg.EventType`` has dual aliases: ``WorkItemOutputFiles`` and ``WorkItemResult`` both map to integer 35 | info | Use ``WorkItemResult`` as the canonical name (matches PDG docs) |
| ``pdg`` module also exposes ``pdg.callback``, ``pdg.scheduler``, ``pdg.workitem`` as **submodules** (not classes) — these contain helper utilities. Distinct from ``pdg.Scheduler`` / ``pdg.WorkItem`` (the pybind11 classes) | warn | Don't confuse ``pdg.scheduler`` (helper module) with ``pdg.Scheduler`` (class). Spike 3.1 imports ``pdg`` and uses capitalised class names |
| ``pdg.WorkItem`` has a ``cancel`` instancemethod — useful for daemon-side cancellation propagation | info | Note for Spike 3.4 (hostile Crucible cancel-mid-cook test) |
| ``pdg.Scheduler.runOnMainThread(self, wait, function, *args, **kwargs)`` exists — built-in main-thread executor. Already-explored territory analogous to SYNAPSE's ``main_thread_exec`` | info | Cross-check whether the bridge can use this for any main-thread dispatch in Spike 3.1+, vs continuing with ``hdefereval`` |
| ``pdg.GraphContext`` exposes ``cancelCook`` and ``pauseCook`` instancemethods | info | Spike 3.4 hostile Crucible — cancellation test surface available |

---

## 4. Implications for Spike 3.1 TopsEventBridge design

**Headline:** Spike 3.1 designs against standalone ``pdg.*`` from the start. Imports follow ``shared/bridge.py:568+`` convention (``import pdg as _pdg`` defensive-imported, with the ``_PDG_AVAILABLE`` flag). Subscription via ``pdg.PyEventHandler`` + ``pdg.EventType.*`` + ``pdg.GraphContext.addEventHandler``. **Every ``hou.pdg.*`` reference in ``CONTINUATION_INSIDE_OUT_TOPS.md`` (lines ~186–280) is rewritten** as part of the Spike 3.1 design pass — see §4.4 open question #1 for whether to patch the artifact pre-3.1 or inside the 3.1 design dispatch.

### 4.1 Required imports & call shapes

| Sketch reference | Verified shape | Action |
|---|---|---|
| ``hou.pdg`` (top-level) | NOT RESOLVABLE — use standalone ``pdg`` module | ``import pdg as _pdg`` (defensive-imported, ``bridge.py:568+`` convention) |
| ``hou.pdg.scheduler`` | NOT RESOLVABLE — ``pdg.Scheduler`` class exists; live schedulers come via ``graph_context.schedulers`` property or ``graph_context.schedulerForName(...)`` | Rename + use ``pdg.Scheduler`` (class) and instance access via ``GraphContext`` |
| ``hou.pdg.workItem`` | NOT RESOLVABLE — ``pdg.WorkItem`` class exists; instances arrive in event payloads as ``event.workItem`` | Rename to ``pdg.WorkItem`` for the type; instance access stays via event |
| ``hou.pdg.GraphContext`` | NOT RESOLVABLE — ``pdg.GraphContext`` class exists (constructible), but live contexts come from ``top_node.getPDGGraphContext()`` | Replace class-reference path with instance-method path per ``bridge.py:616`` R8 pattern |
| ``hou.pdgEventType`` | NOT RESOLVABLE — superseded by ``pdg.EventType`` | All event-type references rewrite to ``_pdg.EventType.CookComplete``, ``.CookError``, etc. |
| ``pdg.PyEventCallback`` | NOT RESOLVABLE — correct name is ``pdg.PyEventHandler`` | If sketch references this name anywhere, rename to ``PyEventHandler`` |
| ``graph_context.addEventHandler(handler)`` | RESOLVED on ``pdg.GraphContext`` (signature not introspectable from pybind11) | Pin to ``bridge.py:637`` R8 calling convention — confirm 1-arg vs 2-arg shape during 3.1 design |
| ``hou.topNodeTypeCategory()`` (call) | RESOLVED — function returning ``NodeTypeCategory`` | Sketch's call shape is correct, no change |

### 4.2 Event payload contract

The sketch's ``_on_workitem_complete`` reads four fields. Each maps to a real ``pdg.WorkItem`` attribute:

| Field read | Verified attribute | Type | Notes |
|---|---|---|---|
| ``event.workItem`` | ``pdg.PyEventHandler`` callback receives an event with ``.workItem`` per R8 pattern | ``pdg.WorkItem`` instance | Confirm event-object shape in Spike 3.1 design |
| ``.node.path()`` | ``pdg.WorkItem.node`` is a property (returns ``pdg.Node``); ``.path()`` is the standard hou-style accessor | string | Verify ``pdg.Node`` exposes ``path()`` at runtime — alternative: ``.name`` property |
| ``.attribValue("frame")`` | ``pdg.WorkItem.attribValue`` instancemethod confirmed | varies | Alternative: ``.frame`` property is more direct (audit confirms it exists) |
| ``.expectedResultData`` (+ ``f.path``) | ``expectedResultData`` property confirmed; element type not introspected | iterable of result-data objects | Element ``.path`` access — verify at first runtime in Spike 3.3 |
| ``.cookDuration`` | property confirmed | scalar (unit not in docstring) | Sketch multiplies ×1000 (assumes seconds) — verify unit at runtime, do NOT pin in design |

### 4.3 Cleanup contract

| Sketch behaviour | Verified shape | Action |
|---|---|---|
| ``hou.hipFile.addEventCallback(...)`` returns a handle stored in ``self._scene_callback_handle`` | **WRONG — returns ``None``.** Removal is by callback-identity | Spike 3.1: store the bound callback method (``self._scene_callback_fn = self._on_hip_event``) and pass that same reference to ``removeEventCallback`` |
| ``hou.hipFile.removeEventCallback(handle)`` | takes the **callback function**, not a handle | Pass the stored callback function reference |
| ``graph_context.removeEventHandler(handler)`` | RESOLVED on ``pdg.GraphContext`` — ``bridge.py:664`` already uses this | OK as written in sketch concept |

### 4.4 Open questions for orchestrator / next ARCHITECT pass

1. **Patch ``CONTINUATION_INSIDE_OUT_TOPS.md`` sketch now, or inside Spike 3.1 design?** The sketch has ~7 wrong references (``hou.pdg.*``, callback-handle assumption). Two options:
   - (a) Patch the artifact in a small docs commit before dispatching 3.1 ARCHITECT — gives the next agent a corrected sketch to read.
   - (b) Defer to the 3.1 design pass — the design doc itself documents every divergence from the sketch, and the artifact gets patched as part of 3.1's commits.
   - **Recommend (b)** — the audit doc + 3.1 design together form the corrected record; patching twice is churn. Mark as orchestrator decision at 3.1 dispatch.

2. **``cookDuration`` unit verification.** Sketch assumes seconds (×1000 to get ms). Audit doesn't introspect numeric values. Spike 3.3 (first TOPS event surface) is the natural place to runtime-verify with a short test cook — flag as runtime test, not design-time pin.

3. **Event-handler registration scope.** Both ``pdg.GraphContext`` and ``pdg.Scheduler`` AND ``pdg.WorkItem`` expose ``addEventHandler``. Bridge sketch registers at GraphContext. Spike 3.1 should pick ONE registration scope per event-type-class — log as design-time decision.

4. **``pdg.Scheduler.runOnMainThread`` vs ``hdefereval``.** ``pdg.Scheduler`` has its own main-thread executor. Spike 3.1 should NOT switch executors (Strangler Fig — keep ``hdefereval``-based flow), but flag for future evaluation if PDG-context tools want the scheduler-aware variant.

---

## 5. Sign-off

Spike 3.0 closes when **all** of the following are true:

- [x] §0 metadata filled in
- [x] §2.1–§2.9 all contain real audit output (no
      ``[paste output here]`` placeholders remain)
- [x] §3 watchlist confirmed/refuted row-by-row, plus new
      findings recorded in §3.2
- [x] §4 implications complete enough that Spike 3.1's ARCHITECT
      pass can write a design against verified surfaces
- [x] No surfaces flagged "blocking" remain unresolved (3 open
      questions logged in §4.4 for orchestrator decision —
      none block 3.1 design opening)

All five boxes checked. **Spike 3.1 design opens.**

*End of audit document. Script: ``spike_3_0_pdg_audit_script.py``. Full report: ``C:\Users\User\spike_3_0_pdg_audit_20260426-104422.txt``.*
