<template>
  <section class="page" data-module="profile_share">
    <header class="page-head">
      <div><h2>画像共享</h2><p class="page-desc">按访问范围裁剪画像投影并共享给合作方：标签快照保存投影版本与共享对象，打开共享快照时按当前授权返回版本内允许的标签值。</p></div>
    </header>

    <div class="analysis-summary">
      <article class="analysis-card" data-testid="kpi-card"><span style="font-size:12px;color:var(--muted)">字段授权</span><strong style="font-size:22px;display:block">{{ grants.length }}</strong></article>
      <article class="analysis-card" data-testid="kpi-card"><span style="font-size:12px;color:var(--muted)">画像投影版本</span><strong style="font-size:22px;display:block">{{ projections.length }}</strong></article>
      <article class="analysis-card" data-testid="kpi-card"><span style="font-size:12px;color:var(--muted)">共享快照</span><strong style="font-size:22px;display:block">{{ shares.length }}</strong></article>
    </div>

    <form class="analysis-form" @submit.prevent="createProjection">
      <label><span>卡片编号</span><input v-model="projectionForm.card_id" placeholder="PC-003" /></label>
      <label><span>共享对象</span><input v-model="projectionForm.partner_id" placeholder="PTN-001" /></label>
      <button class="btn primary" type="submit" data-testid="create-projection">生成画像投影</button>
    </form>

    <form class="analysis-form" @submit.prevent="createShare">
      <label><span>快照编号</span><input v-model="shareForm.snapshot_id" placeholder="SN-003" /></label>
      <label><span>卡片编号</span><input v-model="shareForm.card_id" placeholder="PC-003" /></label>
      <label><span>共享对象</span><input v-model="shareForm.partner_id" placeholder="PTN-001" /></label>
      <button class="btn primary" type="submit" data-testid="create-share">创建共享快照</button>
    </form>

    <h3>字段授权（来源分群 → 合作方）</h3>
    <table class="data-table">
      <thead><tr><th>授权编号</th><th>来源分群</th><th>合作方</th><th>获准字段</th><th>已撤回</th><th>版本</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="g in grants" :key="g.grant_id">
          <td>{{ g.grant_id }}</td><td>{{ g.segment_id }}</td><td>{{ g.partner_id }}</td>
          <td>{{ (g.allowed_tags || []).join(', ') || '—' }}</td>
          <td>{{ (g.revoked_tags || []).join(', ') || '—' }}</td>
          <td>v{{ g.version }}</td>
          <td>
            <button class="btn" @click="revokeField(g, firstAllowed(g))" :disabled="!firstAllowed(g)">撤回首项</button>
          </td>
        </tr>
      </tbody>
    </table>

    <h3>共享快照</h3>
    <table class="data-table">
      <thead><tr><th>共享编号</th><th>快照</th><th>投影版本</th><th>共享对象</th><th>状态</th><th>打开次数</th><th>受控打开</th></tr></thead>
      <tbody>
        <tr v-for="s in shares" :key="s.share_id">
          <td>{{ s.share_id }}</td><td>{{ s.snapshot_id }}</td>
          <td>{{ s.projection_id }} v{{ s.projection_version }}</td>
          <td>{{ s.partner_id }}</td><td>{{ s.status }}</td><td>{{ s.opened_count }}</td>
          <td>
            <select v-model="openAccount"><option v-for="a in accounts" :key="a.account_id" :value="a.account_id">{{ a.account_name }}</option></select>
            <button class="btn" @click="openShare(s.share_id)" data-testid="open-share">打开</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="opened" class="analysis-chart" style="height:auto;padding:16px">
      <template v-if="opened.viewer_role === 'partner'">
        <p><strong>链接状态：</strong>{{ opened.link_status }} · <strong>投影版本：</strong>{{ opened.projection_id }} v{{ opened.projection_version }}</p>
        <p><strong>可见标签：</strong>{{ opened.tags.map((t: any) => t.tag_name).join(', ') || '—' }}</p>
        <p><strong>需重新交付：</strong>{{ opened.redelivery_scope.map((r: any) => `${r.tag_name}(${r.reason})`).join(', ') || '—' }}</p>
        <p style="color:var(--muted)">{{ opened.message }}</p>
      </template>
      <template v-else>
        <p><strong>维护方复查：</strong>{{ opened.card_name }} → {{ opened.partner_name }} · 原始版本 {{ opened.projection_id }} v{{ opened.projection_version }}</p>
        <p><strong>画像稿标签：</strong>{{ opened.original_projection.tag_values.map((t: any) => t.tag_name).join(', ') }}</p>
        <p><strong>当前获准：</strong>{{ opened.current_allowed_tags.join(', ') || '—' }} · <strong>共享记录：</strong>{{ opened.snapshot_shares.length }} 条</p>
      </template>
    </div>
    <p v-if="error" style="color:var(--danger,#c00);text-align:center">{{ error }}</p>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { request } from '@/api/client'
const ENDPOINT = '/api/profile-share'
const grants = ref<any[]>([]); const projections = ref<any[]>([]); const shares = ref<any[]>([]); const accounts = ref<any[]>([])
const opened = ref<any>(null); const error = ref('')
const openAccount = ref('ACC-PTN-001')
const projectionForm = ref({ card_id: 'PC-003', partner_id: 'PTN-001' })
const shareForm = ref({ snapshot_id: 'SN-003', card_id: 'PC-003', partner_id: 'PTN-001' })
function firstAllowed(g: any) { return (g.allowed_tags || [])[0] || '' }
async function refresh() {
  const [g, p, s, a] = await Promise.all([
    request(`${ENDPOINT}/grants`).then(r => r.json()),
    request(`${ENDPOINT}/projections`).then(r => r.json()),
    request(`${ENDPOINT}/shares`).then(r => r.json()),
    request(`${ENDPOINT}/accounts`).then(r => r.json()),
  ])
  grants.value = g.items || []; projections.value = p.items || []; shares.value = s.items || []; accounts.value = a.items || []
}
async function createProjection() {
  error.value = ''
  const res = await request(`${ENDPOINT}/projections`, { method: 'POST', body: JSON.stringify(projectionForm.value) })
  if (!res.ok) { error.value = (await res.json()).detail || '生成失败'; return }
  await refresh()
}
async function createShare() {
  error.value = ''
  const res = await request(`${ENDPOINT}/shares`, { method: 'POST', body: JSON.stringify(shareForm.value) })
  if (!res.ok) { error.value = (await res.json()).detail || '共享失败'; return }
  await refresh()
}
async function revokeField(g: any, field: string) {
  if (!field) return
  error.value = ''
  await request(`${ENDPOINT}/grants/${g.grant_id}/revoke`, { method: 'POST', body: JSON.stringify({ fields: [field] }) })
  await refresh()
}
async function openShare(shareId: string) {
  error.value = ''
  const res = await request(`${ENDPOINT}/shares/${shareId}/open?account_id=${openAccount.value}`)
  const data = await res.json()
  if (!res.ok) { error.value = data.detail || '打开失败'; opened.value = null; return }
  opened.value = data
  await refresh()
}
onMounted(refresh)
</script>
