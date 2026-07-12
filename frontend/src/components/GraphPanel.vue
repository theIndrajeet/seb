<template>
  <div class="graph-panel">
    <div class="panel-header">
      <span class="panel-title">{{ $t('graph.panelTitle') }}</span>
      <!-- 顶部工具栏 (Internal Top Right) -->
      <div class="header-tools">
        <button class="tool-btn" @click="$emit('refresh')" :disabled="loading" :title="$t('graph.refreshGraph')">
          <span class="icon-refresh" :class="{ 'spinning': loading }">↻</span>
          <span class="btn-text">Refresh</span>
        </button>
        <button class="tool-btn" @click="$emit('toggle-maximize')" :title="$t('graph.toggleMaximize')">
          <span class="icon-maximize">⛶</span>
        </button>
      </div>
    </div>

    <div class="graph-container" ref="graphContainer">
      <!-- 图谱可视化 -->
      <div v-if="graphData" class="graph-view">
        <svg ref="graphSvg" class="graph-svg"></svg>

        <!-- 构建中/模拟中提示 -->
        <div v-if="currentPhase === 1 || isSimulating" class="graph-building-hint">
          <div class="memory-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="memory-icon">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-4.04z" />
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-4.04z" />
            </svg>
          </div>
          {{ isSimulating ? $t('graph.graphMemoryRealtime') : $t('graph.realtimeUpdating') }}
        </div>

        <!-- 模拟结束后的提示 -->
        <div v-if="showSimulationFinishedHint" class="graph-building-hint finished-hint">
          <div class="hint-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="hint-icon">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
          </div>
          <span class="hint-text">{{ $t('graph.pendingContentHint') }}</span>
          <button class="hint-close-btn" @click="dismissFinishedHint" :title="$t('graph.closeHint')">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <!-- 节点/边详情面板 -->
        <div v-if="selectedItem" class="detail-panel">
          <div class="detail-panel-header">
            <span class="detail-title">{{ selectedItem.type === 'node' ? $t('graph.nodeDetails') : $t('graph.relationship') }}</span>
            <span v-if="selectedItem.type === 'node'" class="detail-type-badge" :style="{ background: selectedItem.color, color: '#0b0b17' }">
              {{ selectedItem.entityType }}
            </span>
            <button class="detail-close" @click="closeDetailPanel">×</button>
          </div>

          <!-- 节点详情 -->
          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <div class="detail-row">
              <span class="detail-label">Name:</span>
              <span class="detail-value">{{ selectedItem.data.name }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">UUID:</span>
              <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.created_at">
              <span class="detail-label">Created:</span>
              <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
            </div>

            <!-- Properties -->
            <div class="detail-section" v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length > 0">
              <div class="section-title">Properties:</div>
              <div class="properties-list">
                <div v-for="(value, key) in selectedItem.data.attributes" :key="key" class="property-item">
                  <span class="property-key">{{ key }}:</span>
                  <span class="property-value">{{ value || 'None' }}</span>
                </div>
              </div>
            </div>

            <!-- Summary -->
            <div class="detail-section" v-if="selectedItem.data.summary">
              <div class="section-title">Summary:</div>
              <div class="summary-text">{{ selectedItem.data.summary }}</div>
            </div>

            <!-- Labels -->
            <div class="detail-section" v-if="selectedItem.data.labels && selectedItem.data.labels.length > 0">
              <div class="section-title">Labels:</div>
              <div class="labels-list">
                <span v-for="label in selectedItem.data.labels" :key="label" class="label-tag">
                  {{ label }}
                </span>
              </div>
            </div>
          </div>

          <!-- 边详情 -->
          <div v-else class="detail-content">
            <!-- 自环组详情 -->
            <template v-if="selectedItem.data.isSelfLoopGroup">
              <div class="edge-relation-header self-loop-header">
                {{ selectedItem.data.source_name }} - Self Relations
                <span class="self-loop-count">{{ selectedItem.data.selfLoopCount }} items</span>
              </div>

              <div class="self-loop-list">
                <div
                  v-for="(loop, idx) in selectedItem.data.selfLoopEdges"
                  :key="loop.uuid || idx"
                  class="self-loop-item"
                  :class="{ expanded: expandedSelfLoops.has(loop.uuid || idx) }"
                >
                  <div
                    class="self-loop-item-header"
                    @click="toggleSelfLoop(loop.uuid || idx)"
                  >
                    <span class="self-loop-index">#{{ idx + 1 }}</span>
                    <span class="self-loop-name">{{ loop.name || loop.fact_type || 'RELATED' }}</span>
                    <span class="self-loop-toggle">{{ expandedSelfLoops.has(loop.uuid || idx) ? '−' : '+' }}</span>
                  </div>

                  <div class="self-loop-item-content" v-show="expandedSelfLoops.has(loop.uuid || idx)">
                    <div class="detail-row" v-if="loop.uuid">
                      <span class="detail-label">UUID:</span>
                      <span class="detail-value uuid-text">{{ loop.uuid }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact">
                      <span class="detail-label">Fact:</span>
                      <span class="detail-value fact-text">{{ loop.fact }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact_type">
                      <span class="detail-label">Type:</span>
                      <span class="detail-value">{{ loop.fact_type }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.created_at">
                      <span class="detail-label">Created:</span>
                      <span class="detail-value">{{ formatDateTime(loop.created_at) }}</span>
                    </div>
                    <div v-if="loop.episodes && loop.episodes.length > 0" class="self-loop-episodes">
                      <span class="detail-label">Episodes:</span>
                      <div class="episodes-list compact">
                        <span v-for="ep in loop.episodes" :key="ep" class="episode-tag small">{{ ep }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <!-- 普通边详情 -->
            <template v-else>
              <div class="edge-relation-header">
                {{ selectedItem.data.source_name }} → {{ selectedItem.data.name || 'RELATED_TO' }} → {{ selectedItem.data.target_name }}
              </div>

              <div class="detail-row">
                <span class="detail-label">UUID:</span>
                <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Label:</span>
                <span class="detail-value">{{ selectedItem.data.name || 'RELATED_TO' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Type:</span>
                <span class="detail-value">{{ selectedItem.data.fact_type || 'Unknown' }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.fact">
                <span class="detail-label">Fact:</span>
                <span class="detail-value fact-text">{{ selectedItem.data.fact }}</span>
              </div>

              <!-- Episodes -->
              <div class="detail-section" v-if="selectedItem.data.episodes && selectedItem.data.episodes.length > 0">
                <div class="section-title">Episodes:</div>
                <div class="episodes-list">
                  <span v-for="ep in selectedItem.data.episodes" :key="ep" class="episode-tag">
                    {{ ep }}
                  </span>
                </div>
              </div>

              <div class="detail-row" v-if="selectedItem.data.created_at">
                <span class="detail-label">Created:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.valid_at">
                <span class="detail-label">Valid From:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.valid_at) }}</span>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-else-if="loading" class="graph-state">
        <div class="loading-spinner"></div>
        <p>{{ $t('graph.graphDataLoading') }}</p>
      </div>

      <!-- 等待/空状态 -->
      <div v-else class="graph-state">
        <div class="empty-icon">❖</div>
        <p class="empty-text">{{ $t('graph.waitingOntology') }}</p>
      </div>
    </div>

    <!-- 底部图例 (Bottom Left) -->
    <div v-if="graphData && entityTypes.length" class="graph-legend">
      <span class="legend-title">Entity Types</span>
      <div class="legend-items">
        <div class="legend-item" v-for="type in entityTypes" :key="type.name">
          <span class="legend-dot" :style="{ background: type.color }"></span>
          <span class="legend-label">{{ type.name }}</span>
        </div>
      </div>
    </div>

    <!-- 显示边标签开关 -->
    <div v-if="graphData" class="edge-labels-toggle">
      <label class="toggle-switch">
        <input type="checkbox" v-model="showEdgeLabels" />
        <span class="slider"></span>
      </label>
      <span class="toggle-label">Show Edge Labels</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  currentPhase: Number,
  isSimulating: Boolean
})

const emit = defineEmits(['refresh', 'toggle-maximize'])

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedItem = ref(null)
const showEdgeLabels = ref(true) // 默认显示边标签
const expandedSelfLoops = ref(new Set()) // 展开的自环项
const showSimulationFinishedHint = ref(false) // 模拟结束后的提示
const wasSimulating = ref(false) // 追踪之前是否在模拟中

// 关闭模拟结束提示
const dismissFinishedHint = () => {
  showSimulationFinishedHint.value = false
}

// 监听 isSimulating 变化，检测模拟结束
watch(() => props.isSimulating, (newValue, oldValue) => {
  if (wasSimulating.value && !newValue) {
    // 从模拟中变为非模拟状态，显示结束提示
    showSimulationFinishedHint.value = true
  }
  wasSimulating.value = newValue
}, { immediate: true })

// 切换自环项展开/折叠状态
const toggleSelfLoop = (id) => {
  const newSet = new Set(expandedSelfLoops.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSelfLoops.value = newSet
}

// ============ 案件图谱语义配置 (Case-map semantics) ============

// 亮色系实体类型调色板（深色背景可读）
const TYPE_COLORS = {
  Party: '#a78bfa',
  Counsel: '#c4b5fd',
  Claim: '#f472b6',
  Contract: '#fbbf24',
  Evidence: '#34d399',
  LegalAuthority: '#60a5fa',
  Witness: '#22d3ee',
  Expert: '#22d3ee',
  Person: '#94a3b8',
  Organization: '#fb923c'
}
const FALLBACK_COLOR = '#64748b'
const getColor = (type) => TYPE_COLORS[type] || FALLBACK_COLOR

// 类型语义分区：Claims 居中；Party/Counsel 靠左；Evidence/Witness 靠右；Contract/LegalAuthority 底部居中
const TYPE_ZONES = {
  Claim: { x: 0.50, y: 0.44 },
  Party: { x: 0.16, y: 0.38 },
  Counsel: { x: 0.14, y: 0.64 },
  Person: { x: 0.28, y: 0.52 },
  Organization: { x: 0.30, y: 0.26 },
  Evidence: { x: 0.84, y: 0.38 },
  Witness: { x: 0.86, y: 0.64 },
  Expert: { x: 0.86, y: 0.64 },
  Contract: { x: 0.42, y: 0.84 },
  LegalAuthority: { x: 0.60, y: 0.84 }
}
const getZone = (type) => TYPE_ZONES[type] || { x: 0.5, y: 0.5 }

// 基础样式常量
const EDGE_STROKE = 'rgba(255, 255, 255, 0.18)'
const EDGE_STROKE_HOVER = 'rgba(255, 255, 255, 0.55)'
const EDGE_STROKE_SELECTED = '#818cf8'
const EDGE_LABEL_FILL = '#9ca3af'
const EDGE_LABEL_BG = 'rgba(10, 10, 25, 0.85)'
const NODE_STROKE = 'rgba(255, 255, 255, 0.35)'
const NODE_STROKE_SELECTED = '#22d3ee'
const DIM_OPACITY = 0.15
const LABEL_DENSITY_CAP = 150 // 节点数超过此值时按度数筛选标签

// 计算实体类型用于图例（固定语义调色板）
const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}
  props.graphData.nodes.forEach(node => {
    const type = node.labels?.find(l => l !== 'Entity') || 'Entity'
    if (!typeMap[type]) {
      typeMap[type] = { name: type, count: 0, color: getColor(type) }
    }
    typeMap[type].count++
  })
  return Object.values(typeMap)
})

// 格式化时间
const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    })
  } catch {
    return dateStr
  }
}

const closeDetailPanel = () => {
  selectedItem.value = null
  expandedSelfLoops.value = new Set() // 重置展开状态
}

let currentSimulation = null
let linkLabelsRef = null
let linkLabelBgRef = null
let positionEdgeLabelsRef = null

// 结构签名缓存：轮询数据未变化时不重跑布局
let lastGraphSignature = ''
const lastPositions = new Map()

const computeGraphSignature = (data) => {
  const n = (data?.nodes || []).map(x => x.uuid).sort().join(',')
  const e = (data?.edges || [])
    .map(x => x.uuid || `${x.source_node_uuid}>${x.target_node_uuid}:${x.name || x.fact_type || ''}`)
    .sort().join(',')
  return `${n}#${e}`
}

const renderGraph = () => {
  if (!graphSvg.value || !props.graphData) return

  // 保存旧位置，供增量更新时复用（避免整图重排跳动）
  if (currentSimulation) {
    currentSimulation.nodes().forEach(n => lastPositions.set(n.id, { x: n.x, y: n.y }))
    currentSimulation.stop()
  }

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight
  if (!width || !height) return

  const svg = d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)

  svg.selectAll('*').remove()

  const nodesData = props.graphData.nodes || []
  const edgesData = props.graphData.edges || []

  if (nodesData.length === 0) return

  // Prep data
  const nodeMap = {}
  nodesData.forEach(n => nodeMap[n.uuid] = n)

  const seededCount = { value: 0 }
  const nodes = nodesData.map(n => {
    const prev = lastPositions.get(n.uuid)
    if (prev) seededCount.value++
    return {
      id: n.uuid,
      name: n.name || 'Unnamed',
      type: n.labels?.find(l => l !== 'Entity') || 'Entity',
      rawData: n,
      ...(prev ? { x: prev.x, y: prev.y } : {})
    }
  })

  const nodeIds = new Set(nodes.map(n => n.id))

  // 处理边数据，计算同一对节点间的边数量和索引
  const edgePairCount = {}
  const selfLoopEdges = {} // 按节点分组的自环边
  const tempEdges = edgesData
    .filter(e => nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid))

  // 统计每对节点之间的边数量，收集自环边
  tempEdges.forEach(e => {
    if (e.source_node_uuid === e.target_node_uuid) {
      // 自环 - 收集到数组中
      if (!selfLoopEdges[e.source_node_uuid]) {
        selfLoopEdges[e.source_node_uuid] = []
      }
      selfLoopEdges[e.source_node_uuid].push({
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      })
    } else {
      const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
      edgePairCount[pairKey] = (edgePairCount[pairKey] || 0) + 1
    }
  })

  // 记录当前处理到每对节点的第几条边
  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set() // 已处理的自环节点

  const edges = []

  tempEdges.forEach(e => {
    const isSelfLoop = e.source_node_uuid === e.target_node_uuid

    if (isSelfLoop) {
      // 自环边 - 每个节点只添加一条合并的自环
      if (processedSelfLoopNodes.has(e.source_node_uuid)) {
        return // 已处理过，跳过
      }
      processedSelfLoopNodes.add(e.source_node_uuid)

      const allSelfLoops = selfLoopEdges[e.source_node_uuid]
      const nodeName = nodeMap[e.source_node_uuid]?.name || 'Unknown'

      edges.push({
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        type: 'SELF_LOOP',
        name: `Self Relations (${allSelfLoops.length})`,
        curvature: 0,
        isSelfLoop: true,
        rawData: {
          isSelfLoopGroup: true,
          source_name: nodeName,
          target_name: nodeName,
          selfLoopCount: allSelfLoops.length,
          selfLoopEdges: allSelfLoops // 存储所有自环边的详细信息
        }
      })
      return
    }

    const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1

    // 判断边的方向是否与标准化方向一致（源UUID < 目标UUID）
    const isReversed = e.source_node_uuid > e.target_node_uuid

    // 计算曲率：多条边时分散开，单条边为直线
    let curvature = 0
    if (totalCount > 1) {
      // 均匀分布曲率，确保明显区分
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((currentIndex / (totalCount - 1)) - 0.5) * curvatureRange * 2

      // 如果边的方向与标准化方向相反，翻转曲率
      if (isReversed) {
        curvature = -curvature
      }
    }

    edges.push({
      source: e.source_node_uuid,
      target: e.target_node_uuid,
      type: e.fact_type || e.name || 'RELATED',
      name: e.name || e.fact_type || 'RELATED',
      curvature,
      isSelfLoop: false,
      pairIndex: currentIndex,
      pairTotal: totalCount,
      rawData: {
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      }
    })
  })

  // ===== 度数 → 半径（sqrt 比例尺，6-22px） + 邻接表 =====
  const degreeMap = {}
  const adjacency = new Map()
  nodes.forEach(n => adjacency.set(n.id, new Set()))
  edges.forEach(e => {
    if (e.isSelfLoop) return
    degreeMap[e.source] = (degreeMap[e.source] || 0) + 1
    degreeMap[e.target] = (degreeMap[e.target] || 0) + 1
    adjacency.get(e.source)?.add(e.target)
    adjacency.get(e.target)?.add(e.source)
  })
  const maxDegree = Math.max(1, ...nodes.map(n => degreeMap[n.id] || 0))
  const radiusScale = d3.scaleSqrt().domain([0, maxDegree]).range([6, 22])
  nodes.forEach(n => {
    n.degree = degreeMap[n.id] || 0
    n.radius = radiusScale(n.degree)
  })

  // 大图时的标签密度控制：只显示度数较高的节点标签，其余悬停显示
  const denseGraph = nodes.length > LABEL_DENSITY_CAP
  let labelDegreeThreshold = 0
  if (denseGraph) {
    const sortedDegrees = nodes.map(n => n.degree).sort((a, b) => b - a)
    labelDegreeThreshold = Math.max(1, sortedDegrees[Math.min(LABEL_DENSITY_CAP - 1, sortedDegrees.length - 1)])
  }
  const isLabelVisible = (d) => !denseGraph || d.degree >= labelDegreeThreshold

  // ===== 类型感知力导向布局（语义分区） =====
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      const baseDistance = 130
      const edgeCount = d.pairTotal || 1
      return baseDistance + (edgeCount - 1) * 50
    }))
    .force('charge', d3.forceManyBody().strength(-350))
    .force('collide', d3.forceCollide().radius(d => d.radius + 16))
    // 按实体类型的语义位置聚拢：形成 Claims 中心 / 当事人左侧 / 证据右侧 / 合同与法律依据底部 的可读结构
    .force('x', d3.forceX(d => getZone(d.type).x * width).strength(d => TYPE_ZONES[d.type] ? 0.2 : 0.06))
    .force('y', d3.forceY(d => getZone(d.type).y * height).strength(d => TYPE_ZONES[d.type] ? 0.2 : 0.06))
    .alphaDecay(0.05)

  // 增量更新（大部分节点已有位置）时用低 alpha 微调，避免整图跳动
  if (seededCount.value > 0 && seededCount.value >= nodes.length * 0.8) {
    simulation.alpha(0.3)
  }

  currentSimulation = simulation

  // ===== SVG defs：箭头 marker + Claim 光晕 filter =====
  const defs = svg.append('defs')
  defs.append('marker')
    .attr('id', 'sb-graph-arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 9)
    .attr('refY', 0)
    .attr('markerWidth', 6.5)
    .attr('markerHeight', 6.5)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', 'rgba(255, 255, 255, 0.3)')

  const glowFilter = defs.append('filter')
    .attr('id', 'sb-claim-glow')
    .attr('x', '-60%').attr('y', '-60%')
    .attr('width', '220%').attr('height', '220%')
  glowFilter.append('feGaussianBlur')
    .attr('in', 'SourceGraphic')
    .attr('stdDeviation', 3.5)
    .attr('result', 'blur')
  const glowMerge = glowFilter.append('feMerge')
  glowMerge.append('feMergeNode').attr('in', 'blur')
  glowMerge.append('feMergeNode').attr('in', 'SourceGraphic')

  const g = svg.append('g')

  // Zoom
  svg.call(d3.zoom().extent([[0, 0], [width, height]]).scaleExtent([0.1, 4]).on('zoom', (event) => {
    g.attr('transform', event.transform)
  }))

  // Links - 使用 path 支持曲线
  const linkGroup = g.append('g').attr('class', 'links')

  // 计算曲线路径（终点回缩到目标节点半径外，让箭头可见）
  const getLinkPath = (d) => {
    const sx = d.source.x, sy = d.source.y
    let tx = d.target.x, ty = d.target.y

    // 检测自环
    if (d.isSelfLoop) {
      // 自环：绘制一个圆弧从节点出发再返回
      const loopRadius = 26 + (d.source.radius || 8)
      const r = (d.source.radius || 8)
      const x1 = sx + r * 0.9
      const y1 = sy - r * 0.45
      const x2 = sx + r * 0.9
      const y2 = sy + r * 0.45
      return `M${x1},${y1} A${loopRadius},${loopRadius} 0 1,1 ${x2},${y2}`
    }

    const targetPad = (d.target.radius || 8) + 4

    if (d.curvature === 0) {
      // 直线：终点回缩
      const dx = tx - sx, dy = ty - sy
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      tx = tx - (dx / dist) * targetPad
      ty = ty - (dy / dist) * targetPad
      return `M${sx},${sy} L${tx},${ty}`
    }

    // 计算曲线控制点 - 根据边数量和距离动态调整
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy) || 1
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05 // 基础25%，每多一条边增加5%
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY

    // 沿曲线末端切线方向（控制点 → 终点）回缩终点
    const edx = tx - cx, edy = ty - cy
    const edist = Math.sqrt(edx * edx + edy * edy) || 1
    tx = tx - (edx / edist) * targetPad
    ty = ty - (edy / edist) * targetPad

    return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
  }

  // 计算曲线中点（用于标签定位）
  const getLinkMidpoint = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y

    // 检测自环
    if (d.isSelfLoop) {
      // 自环标签位置：节点右侧
      return { x: sx + 66 + (d.source.radius || 8), y: sy }
    }

    if (d.curvature === 0) {
      return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
    }

    // 二次贝塞尔曲线的中点 t=0.5
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy) || 1
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY

    // 二次贝塞尔曲线公式 B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2, t=0.5
    const midX = 0.25 * sx + 0.5 * cx + 0.25 * tx
    const midY = 0.25 * sy + 0.5 * cy + 0.25 * ty

    return { x: midX, y: midY }
  }

  const link = linkGroup.selectAll('path')
    .data(edges)
    .enter().append('path')
    .attr('stroke', EDGE_STROKE)
    .attr('stroke-width', 1.4)
    .attr('fill', 'none')
    .attr('marker-end', d => d.isSelfLoop ? null : 'url(#sb-graph-arrow)')
    .style('cursor', 'pointer')

  // Link labels background（深色底使文字在暗色画布上清晰）
  const linkLabelBg = linkGroup.selectAll('rect')
    .data(edges)
    .enter().append('rect')
    .attr('fill', EDGE_LABEL_BG)
    .attr('rx', 3)
    .attr('ry', 3)
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('display', showEdgeLabels.value ? 'block' : 'none')

  // Link labels
  const linkLabels = linkGroup.selectAll('text')
    .data(edges)
    .enter().append('text')
    .text(d => d.name)
    .attr('font-size', '9px')
    .attr('fill', EDGE_LABEL_FILL)
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('font-family', 'system-ui, sans-serif')
    .style('display', showEdgeLabels.value ? 'block' : 'none')

  // 保存引用供外部控制显隐
  linkLabelsRef = linkLabels
  linkLabelBgRef = linkLabelBg

  // Nodes group
  const nodeGroup = g.append('g').attr('class', 'nodes')

  // Node circles（半径按度数缩放；Claim 节点附加光晕）
  const node = nodeGroup.selectAll('circle')
    .data(nodes)
    .enter().append('circle')
    .attr('r', d => d.radius)
    .attr('fill', d => getColor(d.type))
    .attr('stroke', NODE_STROKE)
    .attr('stroke-width', 1.5)
    .attr('filter', d => d.type === 'Claim' ? 'url(#sb-claim-glow)' : null)
    .style('cursor', 'pointer')

  // Node Labels（始终可见；大图时按度数抽稀，悬停补显）
  const nodeLabels = nodeGroup.selectAll('text')
    .data(nodes)
    .enter().append('text')
    .text(d => d.name.length > 18 ? d.name.substring(0, 18) + '…' : d.name)
    .attr('font-size', '10.5px')
    .attr('fill', '#e8e8f5')
    .attr('font-weight', '500')
    .attr('dx', d => d.radius + 5)
    .attr('dy', 3.5)
    .attr('stroke', 'rgba(10, 10, 25, 0.85)')
    .attr('stroke-width', 3)
    .attr('stroke-linejoin', 'round')
    .style('paint-order', 'stroke')
    .style('pointer-events', 'none')
    .style('font-family', 'system-ui, sans-serif')
    .style('display', d => isLabelVisible(d) ? 'block' : 'none')

  // ===== 边标签位置更新（tick 内 + 显隐切换后调用） =====
  const positionEdgeLabels = () => {
    linkLabels.each(function(d) {
      if (this.style.display === 'none') return
      const mid = getLinkMidpoint(d)
      d3.select(this)
        .attr('x', mid.x)
        .attr('y', mid.y)
        .attr('transform', '')
    })
    linkLabelBg.each(function(d, i) {
      if (this.style.display === 'none') return
      const textEl = linkLabels.nodes()[i]
      if (!textEl || textEl.style.display === 'none') return
      const mid = getLinkMidpoint(d)
      const bbox = textEl.getBBox()
      d3.select(this)
        .attr('x', mid.x - bbox.width / 2 - 4)
        .attr('y', mid.y - bbox.height / 2 - 2)
        .attr('width', bbox.width + 8)
        .attr('height', bbox.height + 4)
        .attr('transform', '')
    })
  }
  positionEdgeLabelsRef = positionEdgeLabels

  // ===== 基础样式重置 + 选中态重放 =====
  let selectedDatum = null // { kind: 'node' | 'edge', d }

  const applyBaseStyles = () => {
    node.attr('stroke', NODE_STROKE).attr('stroke-width', 1.5).attr('opacity', 1)
    nodeLabels.attr('opacity', 1).style('display', d => isLabelVisible(d) ? 'block' : 'none')
    link.attr('stroke', EDGE_STROKE).attr('stroke-width', 1.4).attr('opacity', 1)
    linkLabels.attr('fill', EDGE_LABEL_FILL).attr('opacity', 1)
    linkLabelBg.attr('fill', EDGE_LABEL_BG).attr('opacity', 1)
    applyEdgeLabelVisibility()
  }

  const applySelectionStyles = () => {
    if (!selectedDatum) return
    if (selectedDatum.kind === 'node') {
      const id = selectedDatum.d.id
      node.filter(n => n.id === id)
        .attr('stroke', NODE_STROKE_SELECTED)
        .attr('stroke-width', 3)
      link.filter(l => l.source.id === id || l.target.id === id)
        .attr('stroke', NODE_STROKE_SELECTED)
        .attr('stroke-width', 2.2)
    } else {
      link.filter(l => l === selectedDatum.d)
        .attr('stroke', EDGE_STROKE_SELECTED)
        .attr('stroke-width', 2.6)
      linkLabels.filter(l => l === selectedDatum.d).attr('fill', EDGE_STROKE_SELECTED)
      linkLabelBg.filter(l => l === selectedDatum.d).attr('fill', 'rgba(129, 140, 248, 0.25)')
    }
  }

  function applyEdgeLabelVisibility() {
    const disp = showEdgeLabels.value ? 'block' : 'none'
    linkLabels.style('display', disp)
    linkLabelBg.style('display', disp)
    if (showEdgeLabels.value) positionEdgeLabels()
  }

  const resetStyles = () => {
    applyBaseStyles()
    applySelectionStyles()
  }

  // ===== 边交互：点击选中 + 悬停高亮/临时显示标签 =====
  const selectEdge = (event, d) => {
    event.stopPropagation()
    selectedDatum = { kind: 'edge', d }
    resetStyles()
    selectedItem.value = { type: 'edge', data: d.rawData }
  }

  const edgeHoverIn = (event, d) => {
    link.filter(l => l === d)
      .attr('stroke', EDGE_STROKE_HOVER)
      .attr('stroke-width', 2)
      .attr('opacity', 1)
    // 悬停边时始终显示该边标签（即使全局标签关闭）
    linkLabels.filter(l => l === d).style('display', 'block').attr('fill', '#e8e8f5')
    linkLabelBg.filter(l => l === d).style('display', 'block')
    positionEdgeLabels()
  }

  const edgeHoverOut = () => {
    resetStyles()
  }

  link
    .on('click', selectEdge)
    .on('mouseenter', edgeHoverIn)
    .on('mouseleave', edgeHoverOut)
  linkLabelBg
    .on('click', selectEdge)
    .on('mouseenter', edgeHoverIn)
    .on('mouseleave', edgeHoverOut)
  linkLabels
    .on('click', selectEdge)
    .on('mouseenter', edgeHoverIn)
    .on('mouseleave', edgeHoverOut)

  // ===== 节点交互：拖拽 / 点击 / 悬停高亮邻居 =====
  node
    .call(d3.drag()
      .on('start', (event, d) => {
        // 只记录位置，不重启仿真（区分点击和拖拽）
        d.fx = d.x
        d.fy = d.y
        d._dragStartX = event.x
        d._dragStartY = event.y
        d._isDragging = false
      })
      .on('drag', (event, d) => {
        // 检测是否真正开始拖拽（移动超过阈值）
        const dx = event.x - d._dragStartX
        const dy = event.y - d._dragStartY
        const distance = Math.sqrt(dx * dx + dy * dy)

        if (!d._isDragging && distance > 3) {
          // 首次检测到真正拖拽，才重启仿真（并重置 tick 上限）
          d._isDragging = true
          tickCount = 0
          simulation.alphaTarget(0.3).restart()
        }

        if (d._isDragging) {
          d.fx = event.x
          d.fy = event.y
        }
      })
      .on('end', (event, d) => {
        // 只有真正拖拽过才让仿真逐渐停止
        if (d._isDragging) {
          simulation.alphaTarget(0)
        }
        d.fx = null
        d.fy = null
        d._isDragging = false
      })
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      selectedDatum = { kind: 'node', d }
      resetStyles()
      selectedItem.value = {
        type: 'node',
        data: d.rawData,
        entityType: d.type,
        color: getColor(d.type)
      }
    })
    .on('mouseenter', (event, d) => {
      const neighbors = adjacency.get(d.id) || new Set()
      const isRelatedNode = (n) => n.id === d.id || neighbors.has(n.id)
      const isRelatedLink = (l) => l.source.id === d.id || l.target.id === d.id

      // 高亮邻居，弱化其余
      node.attr('opacity', n => isRelatedNode(n) ? 1 : DIM_OPACITY)
      node.filter(n => n.id === d.id).attr('stroke', '#ffffff').attr('stroke-width', 2.5)
      nodeLabels
        .attr('opacity', n => isRelatedNode(n) ? 1 : DIM_OPACITY)
        .style('display', n => (isRelatedNode(n) || isLabelVisible(n)) ? 'block' : 'none')
      link
        .attr('opacity', l => isRelatedLink(l) ? 1 : DIM_OPACITY)
        .attr('stroke', l => isRelatedLink(l) ? EDGE_STROKE_HOVER : EDGE_STROKE)
      linkLabels.attr('opacity', l => isRelatedLink(l) ? 1 : DIM_OPACITY)
      linkLabelBg.attr('opacity', l => isRelatedLink(l) ? 1 : DIM_OPACITY)
    })
    .on('mouseleave', () => {
      resetStyles()
    })

  // ===== tick：位置更新 + 稳定后停止 =====
  let tickCount = 0
  simulation.on('tick', () => {
    tickCount++
    if (tickCount > 300) {
      simulation.stop()
      return
    }

    // 更新曲线路径
    link.attr('d', d => getLinkPath(d))

    // 更新边标签位置（无旋转，水平显示更清晰）
    positionEdgeLabels()

    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)

    nodeLabels
      .attr('x', d => d.x)
      .attr('y', d => d.y)
  })

  simulation.on('end', () => {
    nodes.forEach(n => lastPositions.set(n.id, { x: n.x, y: n.y }))
  })

  // 点击空白处关闭详情面板
  svg.on('click', () => {
    selectedItem.value = null
    selectedDatum = null
    resetStyles()
  })
}

watch(() => props.graphData, () => {
  if (!props.graphData) return
  // 数据轮询去抖：节点/边集合未变时跳过重新布局
  const signature = computeGraphSignature(props.graphData)
  if (signature === lastGraphSignature && currentSimulation) return
  lastGraphSignature = signature
  nextTick(renderGraph)
}, { deep: true })

// 监听边标签显示开关
watch(showEdgeLabels, (newVal) => {
  if (linkLabelsRef) {
    linkLabelsRef.style('display', newVal ? 'block' : 'none')
  }
  if (linkLabelBgRef) {
    linkLabelBgRef.style('display', newVal ? 'block' : 'none')
  }
  // 仿真可能已停止，切换后需手动刷新标签位置
  if (newVal && positionEdgeLabelsRef) {
    positionEdgeLabelsRef()
  }
})

const handleResize = () => {
  nextTick(renderGraph)
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  if (props.graphData) {
    lastGraphSignature = computeGraphSignature(props.graphData)
    nextTick(renderGraph)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (currentSimulation) {
    currentSimulation.stop()
  }
})
</script>

<style scoped>
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  background: rgba(10, 10, 25, 0.5);
  overflow: hidden;
}

.panel-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 16px 20px;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to bottom, rgba(11, 11, 23, 0.85), rgba(11, 11, 23, 0));
  pointer-events: none;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  font-family: var(--sb-font-display);
  color: var(--sb-text);
  pointer-events: auto;
}

.header-tools {
  pointer-events: auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.tool-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--sb-glass-border);
  background: var(--sb-glass);
  backdrop-filter: blur(var(--sb-glass-blur));
  -webkit-backdrop-filter: blur(var(--sb-glass-blur));
  border-radius: var(--sb-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  color: var(--sb-text-secondary);
  transition: all 0.2s;
  box-shadow: var(--sb-shadow);
  font-size: 13px;
}

.tool-btn:hover {
  background: var(--sb-glass-strong);
  color: var(--sb-text);
  border-color: var(--sb-glass-border-strong);
}

.tool-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tool-btn .btn-text {
  font-size: 12px;
}

.icon-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.graph-container {
  width: 100%;
  height: 100%;
}

.graph-view, .graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.graph-svg {
  background: transparent;
}

.graph-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: var(--sb-text-muted);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.3;
  color: var(--sb-text-secondary);
}

/* Entity Types Legend - Bottom Left */
.graph-legend {
  position: absolute;
  bottom: 24px;
  left: 24px;
  background: rgba(18, 18, 34, 0.75);
  padding: 12px 16px;
  border-radius: var(--sb-radius-sm);
  border: 1px solid var(--sb-glass-border);
  backdrop-filter: blur(var(--sb-glass-blur));
  -webkit-backdrop-filter: blur(var(--sb-glass-blur));
  box-shadow: var(--sb-shadow);
  z-index: 10;
}

.legend-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #a78bfa;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  max-width: 320px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--sb-text-secondary);
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 6px rgba(255, 255, 255, 0.15);
}

.legend-label {
  white-space: nowrap;
}

/* Edge Labels Toggle - Top Right */
.edge-labels-toggle {
  position: absolute;
  top: 60px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(18, 18, 34, 0.75);
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid var(--sb-glass-border);
  backdrop-filter: blur(var(--sb-glass-blur));
  -webkit-backdrop-filter: blur(var(--sb-glass-blur));
  box-shadow: var(--sb-shadow);
  z-index: 10;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.15);
  border-radius: 22px;
  transition: 0.3s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: var(--sb-text);
  border-radius: 50%;
  transition: 0.3s;
}

input:checked + .slider {
  background: var(--sb-gradient);
}

input:checked + .slider:before {
  transform: translateX(18px);
  background-color: #ffffff;
}

.toggle-label {
  font-size: 12px;
  color: var(--sb-text-secondary);
}

/* Detail Panel - Right Side */
.detail-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 320px;
  max-height: calc(100% - 100px);
  background: rgba(18, 18, 34, 0.88);
  border: 1px solid var(--sb-glass-border);
  border-radius: var(--sb-radius-sm);
  backdrop-filter: blur(var(--sb-glass-blur));
  -webkit-backdrop-filter: blur(var(--sb-glass-blur));
  box-shadow: var(--sb-shadow);
  overflow: hidden;
  font-family: var(--sb-font-body);
  font-size: 13px;
  z-index: 20;
  display: flex;
  flex-direction: column;
}

.detail-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.04);
  border-bottom: 1px solid var(--sb-glass-border);
  flex-shrink: 0;
}

.detail-title {
  font-weight: 600;
  color: var(--sb-text);
  font-size: 14px;
}

.detail-type-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  margin-left: auto;
  margin-right: 12px;
}

.detail-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: var(--sb-text-muted);
  line-height: 1;
  padding: 0;
  transition: color 0.2s;
}

.detail-close:hover {
  color: var(--sb-text);
}

.detail-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.detail-row {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.detail-label {
  color: var(--sb-text-muted);
  font-size: 12px;
  font-weight: 500;
  min-width: 80px;
}

.detail-value {
  color: var(--sb-text);
  flex: 1;
  word-break: break-word;
}

.detail-value.uuid-text {
  font-family: var(--sb-font-mono);
  font-size: 11px;
  color: var(--sb-text-secondary);
}

.detail-value.fact-text {
  line-height: 1.5;
  color: var(--sb-text-secondary);
}

.detail-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--sb-glass-border);
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--sb-text-secondary);
  margin-bottom: 10px;
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.property-item {
  display: flex;
  gap: 8px;
}

.property-key {
  color: var(--sb-text-muted);
  font-weight: 500;
  min-width: 90px;
}

.property-value {
  color: var(--sb-text);
  flex: 1;
}

.summary-text {
  line-height: 1.6;
  color: var(--sb-text-secondary);
  font-size: 12px;
}

.labels-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.label-tag {
  display: inline-block;
  padding: 4px 12px;
  background: var(--sb-glass);
  border: 1px solid var(--sb-glass-border);
  border-radius: 16px;
  font-size: 11px;
  color: var(--sb-text-secondary);
}

.episodes-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.episode-tag {
  display: inline-block;
  padding: 6px 10px;
  background: var(--sb-glass);
  border: 1px solid var(--sb-glass-border);
  border-radius: 6px;
  font-family: var(--sb-font-mono);
  font-size: 10px;
  color: var(--sb-text-secondary);
  word-break: break-all;
}

/* Edge relation header */
.edge-relation-header {
  background: var(--sb-glass);
  border: 1px solid var(--sb-glass-border);
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--sb-text);
  line-height: 1.5;
  word-break: break-word;
}

/* Building hint */
.graph-building-hint {
  position: absolute;
  bottom: 160px; /* Moved up from 80px */
  left: 50%;
  transform: translateX(-50%);
  background: rgba(11, 11, 23, 0.75);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  color: var(--sb-text);
  padding: 10px 20px;
  border-radius: 30px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: var(--sb-shadow);
  border: 1px solid var(--sb-glass-border);
  font-weight: 500;
  letter-spacing: 0.5px;
  z-index: 100;
}

.memory-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  animation: breathe 2s ease-in-out infinite;
}

.memory-icon {
  width: 18px;
  height: 18px;
  color: var(--sb-success);
}

@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: scale(1); filter: drop-shadow(0 0 2px rgba(52, 211, 153, 0.3)); }
  50% { opacity: 1; transform: scale(1.15); filter: drop-shadow(0 0 8px rgba(52, 211, 153, 0.6)); }
}

/* 模拟结束后的提示样式 */
.graph-building-hint.finished-hint {
  background: rgba(11, 11, 23, 0.75);
  border: 1px solid var(--sb-glass-border);
}

.finished-hint .hint-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
}

.finished-hint .hint-icon {
  width: 18px;
  height: 18px;
  color: var(--sb-text);
}

.finished-hint .hint-text {
  flex: 1;
  white-space: nowrap;
}

.hint-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: rgba(255, 255, 255, 0.12);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  color: var(--sb-text);
  transition: all 0.2s;
  margin-left: 8px;
  flex-shrink: 0;
}

.hint-close-btn:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: scale(1.1);
}

/* Loading spinner */
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.12);
  border-top-color: var(--sb-violet);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

/* Self-loop styles */
.self-loop-header {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(52, 211, 153, 0.08);
  border: 1px solid rgba(52, 211, 153, 0.25);
}

.self-loop-count {
  margin-left: auto;
  font-size: 11px;
  color: var(--sb-text-secondary);
  background: rgba(255, 255, 255, 0.08);
  padding: 2px 8px;
  border-radius: 10px;
}

.self-loop-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.self-loop-item {
  background: var(--sb-glass);
  border: 1px solid var(--sb-glass-border);
  border-radius: 8px;
}

.self-loop-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: background 0.2s;
}

.self-loop-item-header:hover {
  background: rgba(255, 255, 255, 0.08);
}

.self-loop-item.expanded .self-loop-item-header {
  background: rgba(255, 255, 255, 0.1);
}

.self-loop-index {
  font-size: 10px;
  font-weight: 600;
  color: var(--sb-text-secondary);
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
}

.self-loop-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--sb-text);
  flex: 1;
}

.self-loop-toggle {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--sb-text-secondary);
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  transition: all 0.2s;
}

.self-loop-item.expanded .self-loop-toggle {
  background: rgba(255, 255, 255, 0.18);
  color: var(--sb-text);
}

.self-loop-item-content {
  padding: 12px;
  border-top: 1px solid var(--sb-glass-border);
}

.self-loop-item-content .detail-row {
  margin-bottom: 8px;
}

.self-loop-item-content .detail-label {
  font-size: 11px;
  min-width: 60px;
}

.self-loop-item-content .detail-value {
  font-size: 12px;
}

.self-loop-episodes {
  margin-top: 8px;
}

.episodes-list.compact {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 4px;
}

.episode-tag.small {
  padding: 3px 6px;
  font-size: 9px;
}
</style>
