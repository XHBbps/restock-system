<template>
  <div class="detail-view">
    <el-card v-if="suggestion" shadow="never">
      <template #header>
        <div class="header-row">
          <div>
            <span class="title">建议单 #{{ suggestion.id }}</span>
            <el-tag style="margin-left: 12px">{{ suggestion.status }}</el-tag>
          </div>
          <div class="actions">
            <el-button @click="$router.back()">返回</el-button>
          </div>
        </div>
      </template>

      <el-collapse v-model="expanded">
        <el-collapse-item
          v-for="item in suggestion.items"
          :key="item.id"
          :name="item.id"
        >
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
                <span class="stat-label">总采购</span>
                <strong>{{ item.total_qty }}</strong>
              </div>
            </div>
          </template>

          <div class="item-body">
            <div class="section">
              <div class="section-title">总采购量</div>
              <el-input-number
                v-model="editing[item.id].total_qty"
                :min="0"
                size="small"
              />
            </div>

            <div class="section">
              <div class="section-title">各国分量 / 各仓分量</div>
              <el-table :data="countryRows(item)" size="small">
                <el-table-column prop="country" label="国家" width="80" />
                <el-table-column prop="qty" label="国家总量" width="100" />
                <el-table-column label="各仓明细">
                  <template #default="{ row }">
                    <span
                      v-for="(wq, w) in row.warehouses"
                      :key="w"
                      class="warehouse-chip"
                    >
                      {{ w }}: {{ wq }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="t_purchase" label="T_采购" width="120" />
                <el-table-column prop="t_ship" label="T_发货" width="120" />
              </el-table>
            </div>

            <div v-if="item.overstock_countries?.length" class="section">
              <div class="section-title">积压国家（只读）</div>
              <el-tag
                v-for="c in item.overstock_countries"
                :key="c"
                type="warning"
                size="small"
                style="margin-right: 8px"
              >{{ c }}</el-tag>
            </div>

            <div class="section">
              <el-button
                type="primary"
                size="small"
                :disabled="!hasChanges(item)"
                @click="save(item)"
              >
                保存修改
              </el-button>
              <el-tag v-if="item.push_blocker" type="info" style="margin-left: 12px">
                {{ item.push_blocker }}
              </el-tag>
              <el-tag
                v-if="item.saihu_po_number"
                type="success"
                style="margin-left: 12px"
              >赛狐采购单号: {{ item.saihu_po_number }}</el-tag>
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
  type SuggestionDetail,
  type SuggestionItem
} from '@/api/suggestion'
import SkuCard from '@/components/SkuCard.vue'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const suggestion = ref<SuggestionDetail | null>(null)
const expanded = ref<number[]>([])
const editing = reactive<Record<number, { total_qty: number }>>({})

async function load(): Promise<void> {
  const id = Number(route.params.id)
  suggestion.value = await getSuggestion(id)
  for (const it of suggestion.value.items) {
    editing[it.id] = { total_qty: it.total_qty }
  }
}

interface CountryRow {
  country: string
  qty: number
  warehouses: Record<string, number>
  t_purchase: string
  t_ship: string
}

function countryRows(item: SuggestionItem): CountryRow[] {
  return Object.entries(item.country_breakdown).map(([country, qty]) => ({
    country,
    qty,
    warehouses: item.warehouse_breakdown[country] || {},
    t_purchase: item.t_purchase[country] || '',
    t_ship: item.t_ship[country] || ''
  }))
}

function hasChanges(item: SuggestionItem): boolean {
  return editing[item.id]?.total_qty !== item.total_qty
}

async function save(item: SuggestionItem): Promise<void> {
  if (!suggestion.value) return
  try {
    await patchSuggestionItem(suggestion.value.id, item.id, {
      total_qty: editing[item.id].total_qty
    })
    ElMessage.success('已保存')
    item.total_qty = editing[item.id].total_qty
  } catch {
    ElMessage.error('保存失败')
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
.loading {
  text-align: center;
  padding: $space-12;
  color: $color-text-secondary;
}
</style>
