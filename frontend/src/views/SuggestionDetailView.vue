<template>
  <div class="detail-view">
    <el-card v-if="suggestion" shadow="never">
      <template #header>
        <div class="header-row">
          <div>
            <span class="title">建议单 #{{ suggestion.id }}</span>
            <el-tag style="margin-left: 12px" :type="suggestionStatusMeta.tagType">
              {{ suggestionStatusMeta.label }}
            </el-tag>
          </div>
          <div class="actions">
            <el-button @click="$router.back()">返回</el-button>
          </div>
        </div>
      </template>

      <el-collapse v-model="expanded">
        <el-collapse-item v-for="item in suggestion.items" :key="item.id" :name="item.id">
          <template #title>
            <div class="item-header">
              <SkuCard
                :sku="item.commodity_sku"
                :name="item.commodity_name"
                :image="item.main_image"
                :urgent="item.urgent"
                :blocker="item.push_blocker"
              />
              <div class="item-stats">
                <span class="stat-label">总采购量</span>
                <strong>{{ item.total_qty }}</strong>
              </div>
            </div>
          </template>

          <div class="item-body">
            <div class="section">
              <div class="section-title">总采购量</div>
              <el-input-number v-model="editing[item.id].total_qty" :min="0" size="small" />
            </div>

            <div class="section">
              <div class="section-title">各国分量 / 各仓分量</div>
              <el-table :data="countryRows(item)" size="small">
                <el-table-column prop="country" label="国家" width="80" show-overflow-tooltip />
                <el-table-column prop="qty" label="国家总量" width="100" show-overflow-tooltip />
                <el-table-column label="各仓明细" show-overflow-tooltip>
                  <template #default="{ row }">
                    <span v-for="(wq, w) in row.warehouses" :key="w" class="warehouse-chip">
                      {{ w }}: {{ wq }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="拆分依据" min-width="220" show-overflow-tooltip>
                  <template #default="{ row }">
                    <div v-if="row.allocation" class="allocation-meta">
                      <el-tag
                        :type="allocationModeTagType(row.allocation.allocation_mode)"
                        size="small"
                      >
                        {{ allocationModeLabel(row.allocation.allocation_mode) }}
                      </el-tag>
                      <span class="allocation-text">{{ allocationSummary(row.allocation) }}</span>
                      <span class="allocation-text">
                        可用仓：{{ row.allocation.eligible_warehouses.join(', ') || '-' }}
                      </span>
                    </div>
                    <span v-else class="allocation-text">-</span>
                  </template>
                </el-table-column>
                <el-table-column prop="t_purchase" label="采购时间" width="120" show-overflow-tooltip />
                <el-table-column prop="t_ship" label="发货时间" width="120" show-overflow-tooltip />
              </el-table>
            </div>

            <div v-if="item.overstock_countries?.length" class="section">
              <div class="section-title">积压国家（只读）</div>
              <el-tag
                v-for="country in item.overstock_countries"
                :key="country"
                type="warning"
                size="small"
                style="margin-right: 8px"
              >
                {{ country }}
              </el-tag>
            </div>

            <div class="section">
              <el-button type="primary" size="small" :disabled="!hasChanges(item)" @click="save(item)">
                保存修改
              </el-button>
              <el-tag v-if="item.push_blocker" type="info" style="margin-left: 12px">
                {{ item.push_blocker }}
              </el-tag>
              <el-tag
                v-if="item.saihu_po_number"
                type="success"
                style="margin-left: 12px"
              >
                赛狐采购单号：{{ item.saihu_po_number }}
              </el-tag>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <div v-else class="loading">加载中...</div>
  </div>
</template>

<script setup lang="ts">
import {
  getSuggestion,
  patchSuggestionItem,
  type AllocationExplanation,
  type SuggestionDetail,
  type SuggestionItem,
} from '@/api/suggestion'
import SkuCard from '@/components/SkuCard.vue'
import { allocationModeLabel, allocationModeTagType, allocationSummary } from '@/utils/allocation'
import { getSuggestionStatusMeta } from '@/utils/status'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const suggestion = ref<SuggestionDetail | null>(null)
const expanded = ref<number[]>([])
const editing = reactive<Record<number, { total_qty: number }>>({})

const suggestionStatusMeta = computed(() =>
  suggestion.value ? getSuggestionStatusMeta(suggestion.value.status) : { label: '暂无', tagType: 'info' as const },
)

async function load(): Promise<void> {
  const id = Number(route.params.id)
  suggestion.value = await getSuggestion(id)
  for (const item of suggestion.value.items) {
    editing[item.id] = { total_qty: item.total_qty }
  }
}

interface CountryRow {
  country: string
  qty: number
  warehouses: Record<string, number>
  allocation: AllocationExplanation | null
  t_purchase: string
  t_ship: string
}

function countryRows(item: SuggestionItem): CountryRow[] {
  return Object.entries(item.country_breakdown).map(([country, qty]) => ({
    country,
    qty,
    warehouses: item.warehouse_breakdown[country] || {},
    allocation: item.allocation_snapshot?.[country] || null,
    t_purchase: item.t_purchase[country] || '',
    t_ship: item.t_ship[country] || '',
  }))
}

function hasChanges(item: SuggestionItem): boolean {
  return editing[item.id]?.total_qty !== item.total_qty
}

async function save(item: SuggestionItem): Promise<void> {
  if (!suggestion.value) return
  try {
    await patchSuggestionItem(suggestion.value.id, item.id, {
      total_qty: editing[item.id].total_qty,
    })
    ElMessage.success('已保存。')
    item.total_qty = editing[item.id].total_qty
  } catch {
    ElMessage.error('保存失败。')
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.detail-view {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 24px;
}

.item-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;

  .stat-label {
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }

  strong {
    color: $color-brand-primary;
    font-size: $font-size-xl;
  }
}

.item-body {
  padding: $space-4 $space-2;
}

.section {
  margin-bottom: $space-5;
}

.section-title {
  font-weight: $font-weight-medium;
  color: $color-text-secondary;
  margin-bottom: $space-2;
}

.warehouse-chip {
  display: inline-block;
  padding: 2px 8px;
  margin-right: 8px;
  background: $color-brand-primary-soft;
  color: $color-brand-primary;
  border-radius: $radius-pill;
  font-size: $font-size-xs;
}

.allocation-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
}

.allocation-text {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.loading {
  text-align: center;
  padding: $space-12;
  color: $color-text-secondary;
}

@media (max-width: 900px) {
  .header-row,
  .item-header {
    flex-direction: column;
    align-items: flex-start;
    gap: $space-3;
  }
}
</style>
