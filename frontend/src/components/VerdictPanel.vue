<template>
  <div class="verdict-panel sb-glass" v-if="verdict || loading || error">
    <!-- Loading -->
    <div v-if="loading" class="verdict-loading">
      <div class="pulse-dot"></div>
      <span>{{ $t('verdict.loading') }}</span>
    </div>

    <!-- Extract prompt (no verdict yet) -->
    <div v-else-if="error && !verdict" class="verdict-empty">
      <span class="verdict-empty-text">{{ $t('verdict.notExtracted') }}</span>
      <button class="extract-btn" :disabled="extracting" @click="runExtraction">
        {{ extracting ? $t('verdict.extracting') : $t('verdict.extractBtn') }}
      </button>
    </div>

    <!-- Verdict -->
    <template v-else-if="verdict">
      <!-- Outcome banner -->
      <div class="outcome-banner">
        <div class="outcome-headline">
          <span class="gavel-icon">⚖</span>
          <div>
            <h2 class="outcome-title">{{ headlineText }}</h2>
            <p class="outcome-sub">
              {{ verdict.claimant }} <span class="vs">v.</span> {{ verdict.respondent }}
              <span v-if="verdict.governing_law" class="law-chip">{{ verdict.governing_law }}</span>
            </p>
          </div>
        </div>
        <div class="confidence-block" v-if="verdict.headline?.overall_probability != null">
          <div class="confidence-value">{{ Math.round(verdict.headline.overall_probability * 100) }}%</div>
          <div class="confidence-label">{{ $t('verdict.confidence') }}</div>
        </div>
      </div>

      <!-- Per-claim findings -->
      <div class="claims-grid">
        <div v-for="claim in verdict.per_claim" :key="claim.claim_id" class="claim-card">
          <div class="claim-head">
            <span class="claim-title">{{ claim.claim_title }}</span>
            <span class="finding-badge" :class="claim.majority_finding">
              {{ claim.majority_finding === 'claimant' ? $t('verdict.forClaimant') : $t('verdict.forRespondent') }}
            </span>
          </div>
          <div class="claim-meta">
            <span class="vote-split">{{ $t('verdict.voteSplit') }}: {{ claim.vote_split }}{{ claim.unanimous ? ' · ' + $t('verdict.unanimous') : '' }}</span>
            <span class="claim-prob">{{ Math.round(claim.probability * 100) }}%</span>
          </div>
          <div class="prob-bar">
            <div class="prob-fill" :class="claim.majority_finding" :style="{ width: (claim.probability * 100) + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- Arbitrator votes -->
      <div class="ballots-row">
        <div v-for="b in verdict.arbitrator_ballots" :key="b.arbitrator.agent_id" class="ballot-card">
          <div class="ballot-name">{{ b.arbitrator.name }}</div>
          <div class="ballot-philosophy">{{ b.arbitrator.philosophy }}</div>
          <p class="ballot-view">{{ b.ballot.overall_view }}</p>
          <div class="ballot-damages" v-if="b.ballot.damages_awarded != null">
            {{ $t('verdict.awards') }} {{ formatAmount(b.ballot.damages_awarded, b.ballot.damages_currency) }}
          </div>
        </div>
      </div>

      <!-- Damages range -->
      <div class="damages-block" v-if="verdict.damages?.median != null && verdict.damages?.max > 0">
        <div class="damages-label">{{ $t('verdict.damagesRange') }}</div>
        <div class="damages-bar-wrap">
          <span class="damages-min">{{ formatAmount(verdict.damages.min, verdict.damages.currency) }}</span>
          <div class="damages-bar">
            <div class="damages-median" :style="{ left: medianPosition + '%' }">
              <div class="median-tick"></div>
              <div class="median-value">{{ formatAmount(verdict.damages.median, verdict.damages.currency) }}</div>
            </div>
          </div>
          <span class="damages-max">{{ formatAmount(verdict.damages.max, verdict.damages.currency) }}</span>
        </div>
      </div>

      <div class="verdict-disclaimer">{{ $t('verdict.disclaimer') }}</div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getVerdict, extractVerdict } from '../api/simulation'

const props = defineProps({
  simulationId: { type: String, required: true }
})

const verdict = ref(null)
const loading = ref(true)
const error = ref(false)
const extracting = ref(false)

const headlineText = computed(() => {
  const h = verdict.value?.headline
  if (!h) return ''
  return h.claims_for_claimant > 0
    ? `Claimant prevails on ${h.claims_for_claimant} of ${h.claims_total} claim${h.claims_total > 1 ? 's' : ''}`
    : `Respondent prevails on all ${h.claims_total} claim${h.claims_total > 1 ? 's' : ''}`
})

const medianPosition = computed(() => {
  const d = verdict.value?.damages
  if (!d || d.median == null || d.min == null || d.max == null || d.max === d.min) return 50
  return ((d.median - d.min) / (d.max - d.min)) * 100
})

const formatAmount = (amount, currency) => {
  if (amount == null) return '—'
  const formatted = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(amount)
  return currency ? `${currency} ${formatted}` : formatted
}

const fetchVerdict = async () => {
  loading.value = true
  try {
    const res = await getVerdict(props.simulationId)
    if (res?.success) {
      verdict.value = res.data
      error.value = false
    } else {
      error.value = true
    }
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

const runExtraction = async () => {
  extracting.value = true
  try {
    const res = await extractVerdict(props.simulationId)
    if (res?.success) {
      verdict.value = res.data
      error.value = false
    }
  } catch (e) {
    console.error('Verdict extraction failed:', e)
  } finally {
    extracting.value = false
  }
}

onMounted(fetchVerdict)
defineExpose({ refresh: fetchVerdict })
</script>

<style scoped>
.verdict-panel {
  padding: 24px;
  margin-bottom: 24px;
  border-radius: var(--sb-radius-lg);
}

.verdict-loading,
.verdict-empty {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--sb-text-secondary);
  font-size: 14px;
}

.pulse-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--sb-gradient);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.1); }
}

.verdict-empty { justify-content: space-between; }

.extract-btn {
  padding: 8px 18px;
  background: var(--sb-gradient);
  color: #fff;
  border: none;
  border-radius: var(--sb-radius-sm);
  font-family: var(--sb-font-display);
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: opacity 0.2s, box-shadow 0.25s var(--sb-ease);
}
.extract-btn:hover:not(:disabled) { box-shadow: var(--sb-shadow-glow); }
.extract-btn:disabled { opacity: 0.5; cursor: wait; }

/* Outcome banner */
.outcome-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--sb-glass-border);
}

.outcome-headline { display: flex; align-items: center; gap: 16px; }

.gavel-icon {
  font-size: 30px;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: var(--sb-gradient-soft);
  border: 1px solid var(--sb-glass-border-strong);
}

.outcome-title {
  font-family: var(--sb-font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--sb-text);
  margin-bottom: 4px;
}

.outcome-sub { font-size: 13px; color: var(--sb-text-secondary); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.vs { font-style: italic; color: var(--sb-text-muted); }

.law-chip {
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(139, 92, 246, 0.15);
  border: 1px solid rgba(139, 92, 246, 0.35);
  color: #c4b5fd;
  font-size: 11px;
}

.confidence-block { text-align: center; }
.confidence-value {
  font-family: var(--sb-font-display);
  font-size: 34px;
  font-weight: 700;
  background: var(--sb-gradient-text);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.confidence-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--sb-text-muted); }

/* Claims */
.claims-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
  margin: 20px 0;
}

.claim-card {
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--sb-glass-border);
  border-radius: var(--sb-radius);
}

.claim-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 8px; }
.claim-title { font-size: 13px; font-weight: 600; color: var(--sb-text); }

.finding-badge {
  flex-shrink: 0;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.finding-badge.claimant { background: rgba(52, 211, 153, 0.15); color: var(--sb-success); border: 1px solid rgba(52, 211, 153, 0.35); }
.finding-badge.respondent { background: rgba(96, 165, 250, 0.15); color: var(--sb-info); border: 1px solid rgba(96, 165, 250, 0.35); }

.claim-meta { display: flex; justify-content: space-between; font-size: 12px; color: var(--sb-text-muted); margin-bottom: 6px; }
.claim-prob { color: var(--sb-text-secondary); font-weight: 600; }

.prob-bar { height: 6px; background: rgba(255, 255, 255, 0.08); border-radius: 3px; overflow: hidden; }
.prob-fill { height: 100%; border-radius: 3px; transition: width 0.6s var(--sb-ease); }
.prob-fill.claimant { background: linear-gradient(90deg, #34d399, #22d3ee); }
.prob-fill.respondent { background: linear-gradient(90deg, #60a5fa, #818cf8); }

/* Ballots */
.ballots-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.ballot-card {
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--sb-glass-border);
  border-radius: var(--sb-radius);
}

.ballot-name { font-family: var(--sb-font-display); font-size: 13px; font-weight: 700; color: var(--sb-text); }
.ballot-philosophy { font-size: 11px; color: #c4b5fd; text-transform: capitalize; margin: 2px 0 8px; }
.ballot-view { font-size: 12px; line-height: 1.6; color: var(--sb-text-secondary); }
.ballot-damages { margin-top: 8px; font-size: 12px; font-weight: 600; color: var(--sb-warning); }

/* Damages */
.damages-block { margin-bottom: 16px; }
.damages-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--sb-text-muted); margin-bottom: 22px; }
.damages-bar-wrap { display: flex; align-items: center; gap: 12px; }
.damages-min, .damages-max { font-size: 12px; color: var(--sb-text-secondary); white-space: nowrap; }

.damages-bar {
  position: relative;
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: linear-gradient(90deg, rgba(139, 92, 246, 0.35), rgba(99, 102, 241, 0.55), rgba(59, 130, 246, 0.35));
}

.damages-median { position: absolute; top: -14px; transform: translateX(-50%); text-align: center; }
.median-tick { width: 2px; height: 36px; background: #fff; margin: 0 auto; border-radius: 1px; box-shadow: 0 0 8px rgba(255, 255, 255, 0.6); }
.median-value { margin-top: 4px; font-size: 11px; font-weight: 700; color: var(--sb-text); white-space: nowrap; }

.verdict-disclaimer {
  padding-top: 14px;
  border-top: 1px solid var(--sb-glass-border);
  font-size: 11px;
  color: var(--sb-text-muted);
  font-style: italic;
}

@media (max-width: 720px) {
  .outcome-banner { flex-direction: column; align-items: flex-start; }
}
</style>
