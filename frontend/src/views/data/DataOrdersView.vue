<template>
  <PageSectionCard title="订单列表">
    <template #actions>
      <div v-if="!isMobile" class="order-filters desktop-order-filters">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始"
          end-placeholder="结束"
          value-format="YYYY-MM-DD"
          style="width: 260px"
          @change="reloadFirstPage"
        />
        <el-input
          v-model="filters.sku"
          placeholder="SKU / 订单号"
          clearable
          style="width: 220px"
          @input="scheduleSkuReload"
          @keyup.enter="reloadFirstPage"
          @clear="reloadFirstPage"
        />
        <el-select
          v-model="filters.country"
          placeholder="国家"
          clearable
          filterable
          style="width: 140px"
          @change="reloadFirstPage"
        >
          <el-option v-for="c in countryOptions" :key="c.code" :label="c.label" :value="c.code" />
        </el-select>
        <el-select
          v-model="filters.shop"
          placeholder="店铺"
          clearable
          filterable
          style="width: 160px"
          @change="reloadFirstPage"
        >
          <el-option v-for="s in shopOptions" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select
          v-model="filters.platform"
          placeholder="平台"
          clearable
          filterable
          style="width: 150px"
          @change="reloadFirstPage"
        >
          <el-option
            v-for="platform in platformOptions"
            :key="platform"
            :label="platform"
            :value="platform"
          />
        </el-select>
        <el-select
          v-model="filters.status"
          placeholder="包裹状态"
          clearable
          style="width: 150px"
          @change="reloadFirstPage"
        >
          <el-option
            v-for="item in packageStatusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button v-if="canEdit" type="primary" plain @click="openMatchDialog">
          信息匹配
        </el-button>
      </div>
      <div v-else class="mobile-order-actions">
        <el-input
          v-model="filters.sku"
          placeholder="SKU / 订单号"
          clearable
          class="mobile-order-search"
          @input="scheduleSkuReload"
          @keyup.enter="reloadFirstPage"
          @clear="reloadFirstPage"
        />
        <el-button plain class="mobile-filter-trigger" @click="mobileFilterDrawerVisible = true">
          <SlidersHorizontal :size="14" />
          <span>筛选</span>
        </el-button>
        <el-button
          v-if="canEdit"
          type="primary"
          plain
          class="mobile-match-action"
          @click="openMatchDialog"
        >
          信息匹配
        </el-button>
      </div>
    </template>

    <el-drawer
      v-if="isMobile"
      v-model="mobileFilterDrawerVisible"
      title="筛选订单"
      direction="btt"
      size="78%"
      class="mobile-order-filter-drawer"
    >
      <div class="mobile-filter-form">
        <label class="mobile-filter-field">
          <span>日期范围</span>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            @change="reloadFirstPage"
          />
        </label>
        <label class="mobile-filter-field">
          <span>国家</span>
          <el-select
            v-model="filters.country"
            placeholder="国家"
            clearable
            filterable
            @change="reloadFirstPage"
          >
            <el-option v-for="c in countryOptions" :key="c.code" :label="c.label" :value="c.code" />
          </el-select>
        </label>
        <label class="mobile-filter-field">
          <span>店铺</span>
          <el-select
            v-model="filters.shop"
            placeholder="店铺"
            clearable
            filterable
            @change="reloadFirstPage"
          >
            <el-option v-for="s in shopOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </label>
        <label class="mobile-filter-field">
          <span>平台</span>
          <el-select
            v-model="filters.platform"
            placeholder="平台"
            clearable
            filterable
            @change="reloadFirstPage"
          >
            <el-option
              v-for="platform in platformOptions"
              :key="platform"
              :label="platform"
              :value="platform"
            />
          </el-select>
        </label>
        <label class="mobile-filter-field">
          <span>包裹状态</span>
          <el-select
            v-model="filters.status"
            placeholder="包裹状态"
            clearable
            @change="reloadFirstPage"
          >
            <el-option
              v-for="item in packageStatusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </label>
      </div>
      <template #footer>
        <div class="mobile-filter-footer">
          <el-button plain @click="resetMobileFilters">重置筛选</el-button>
          <el-button type="primary" @click="mobileFilterDrawerVisible = false">关闭</el-button>
        </div>
      </template>
    </el-drawer>

    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      table-layout="auto"
      @sort-change="handleSortChange"
    >
      <el-table-column
        label="订单号"
        prop="amazonOrderId"
        min-width="190"
        sortable="custom"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span class="mono nowrap">{{ row.amazonOrderId }}</span>
        </template>
      </el-table-column>
      <el-table-column
        label="店铺"
        prop="shopName"
        min-width="150"
        sortable="custom"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span>{{ row.shopName || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        label="平台"
        prop="orderPlatform"
        min-width="112"
        sortable="custom"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <el-tag size="small" effect="plain" type="info" class="nowrap">
            {{ row.orderPlatform }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="国家" prop="countryCode" width="72" align="center" sortable="custom">
        <template #default="{ row }">
          <el-tag size="small">{{ formatCountryCodeForDisplay(row.countryCode) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="邮编"
        prop="postalCode"
        width="108"
        sortable="custom"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span class="mono nowrap">{{ row.postalCode || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="包裹状态" prop="packageStatus" width="132" sortable="custom">
        <template #default="{ row }">
          <el-tag :type="statusType(row.packageStatus || row.orderStatus)" size="small">
            {{ statusLabel(row.packageStatus || row.orderStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="明细数" prop="itemCount" width="80" align="right" sortable="custom">
        <template #default="{ row }">{{ row.itemCount }}</template>
      </el-table-column>
      <el-table-column label="下单时间" prop="purchaseDate" min-width="168" sortable="custom">
        <template #default="{ row }">
          <span class="muted mono nowrap">
            {{ formatOrderDisplayTime(displayPurchaseDate(row)) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="112" align="center">
        <template #default="{ row }">
          <el-button v-if="canEdit" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <MobileRecordList
      v-else
      :items="rows"
      :loading="loading"
      row-key="amazonOrderId"
      empty-text="暂无订单"
      class="mobile-orders-list"
    >
      <template #default="{ item: row }">
        <div class="mobile-order-card">
          <div class="mobile-card-head">
            <div class="mobile-card-title mono">{{ row.amazonOrderId }}</div>
            <el-tag :type="statusType(row.packageStatus || row.orderStatus)" size="small">
              {{ statusLabel(row.packageStatus || row.orderStatus) }}
            </el-tag>
          </div>
          <div class="mobile-card-meta">
            <span>{{ row.shopName || '-' }}</span>
            <el-tag size="small" effect="plain" type="info">{{ row.orderPlatform }}</el-tag>
            <el-tag size="small">{{ formatCountryCodeForDisplay(row.countryCode) }}</el-tag>
          </div>
          <div class="mobile-kv-grid">
            <div>
              <span>明细数</span>
              <strong>{{ row.itemCount }}</strong>
            </div>
            <div>
              <span>邮编</span>
              <strong class="mono">{{ row.postalCode || '-' }}</strong>
            </div>
            <div class="mobile-kv-grid__wide">
              <span>下单时间</span>
              <strong class="mono">{{ formatOrderDisplayTime(displayPurchaseDate(row)) }}</strong>
            </div>
          </div>
          <div class="mobile-card-actions">
            <el-button v-if="canEdit" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          </div>
        </div>
      </template>
    </MobileRecordList>

    <TablePaginationBar
      v-if="!isMobile"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100, 200]"
      @current-change="handlePageChange"
      @size-change="handlePageSizeChange"
    />

    <div v-if="isMobile" class="mobile-fixed-pagination" aria-label="订单分页">
      <el-button
        plain
        size="small"
        class="mobile-page-prev"
        :disabled="page <= 1"
        @click="goMobilePage(page - 1)"
      >
        上一页
      </el-button>
      <span class="mobile-page-indicator">第 {{ page }} / {{ totalPages }} 页</span>
      <el-button
        plain
        size="small"
        class="mobile-page-next"
        :disabled="page >= totalPages"
        @click="goMobilePage(page + 1)"
      >
        下一页
      </el-button>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="detail ? `订单详情 · ${detail.amazonOrderId}` : '加载中...'"
      width="800px"
      :fullscreen="isMobile"
      class="order-detail-dialog"
    >
      <div v-if="detail" class="detail-body">
        <div class="detail-section">
          <div class="section-title">基本信息</div>
          <div class="kv-grid">
            <div>
              <span class="label">包裹状态</span>
              <span>{{ statusLabel(detail.packageStatus || detail.orderStatus) }}</span>
            </div>
            <div>
              <span class="label">店铺</span>
              <span>{{ detail.shopName || '-' }}</span>
            </div>
            <div>
              <span class="label">平台</span>
              <span>{{ detail.orderPlatform }}</span>
            </div>
            <div>
              <span class="label">国家</span>
              <span class="mono">{{ formatCountryCodeForDisplay(detail.countryCode) }}</span>
            </div>
            <div>
              <span class="label">邮编</span>
              <span class="mono">{{ detail.postalCode || '-' }}</span>
            </div>
            <div>
              <span class="label">订单号</span>
              <span class="mono">{{ detail.amazonOrderId }}</span>
            </div>
            <div>
              <span class="label">下单时间</span>
              <span class="mono">{{ formatOrderDisplayTime(displayPurchaseDate(detail)) }}</span>
            </div>
            <div>
              <span class="label">最后更新时间</span>
              <span class="mono">{{ formatOrderDisplayTime(displayLastUpdateDate(detail)) }}</span>
            </div>
            <div>
              <span class="label">订单金额</span>
              <span class="mono">
                {{
                  detail.orderTotalAmount
                    ? `${detail.orderTotalAmount} ${detail.orderTotalCurrency || ''}`
                    : '-'
                }}
              </span>
            </div>
          </div>
        </div>
        <div class="detail-section">
          <div class="section-title">订单明细（{{ detail.items.length }}）</div>
          <table class="detail-items-table">
            <thead>
              <tr>
                <th>订单商品ID</th>
                <th>商品 SKU</th>
                <th>下单数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in detail.items" :key="item.orderItemId">
                <td class="mono">{{ item.orderItemId }}</td>
                <td>{{ item.commoditySku }}</td>
                <td class="align-right">{{ item.quantityOrdered }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </el-dialog>

    <el-dialog
      v-model="editDialogVisible"
      :title="editDetail ? `编辑订单 · ${editDetail.amazonOrderId}` : '加载中...'"
      width="820px"
      :fullscreen="isMobile"
      class="order-detail-dialog"
    >
      <div v-if="editDetail" class="detail-body">
        <div class="detail-section">
          <div class="section-title">基本信息</div>
          <el-form label-position="top" class="edit-form">
            <el-form-item label="订单号">
              <el-input :model-value="editDetail.amazonOrderId" disabled />
            </el-form-item>
            <el-form-item label="包裹号">
              <el-input :model-value="editDetail.packageSn" disabled />
            </el-form-item>
            <el-form-item label="包裹状态">
              <el-input :model-value="statusLabel(editDetail.packageStatus || editDetail.orderStatus)" disabled />
            </el-form-item>
            <el-form-item label="国家">
              <el-select v-model="editForm.countryCode" filterable allow-create default-first-option>
                <el-option v-for="c in countryOptions" :key="c.code" :label="c.label" :value="c.code" />
              </el-select>
            </el-form-item>
            <el-form-item label="邮编">
              <el-input v-model="editForm.postalCode" />
            </el-form-item>
          </el-form>
        </div>
      </div>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="matchDialogVisible"
      title="订单信息匹配"
      width="860px"
      :fullscreen="isMobile"
      class="order-match-dialog"
      @closed="resetMatchSession"
    >
      <div class="match-body">
        <div class="detail-section">
          <div class="section-title">匹配字段</div>
          <el-checkbox-group v-model="matchSelectedFields" class="field-grid">
            <el-checkbox
              v-for="field in matchFields"
              :key="field.key"
              :label="field.key"
            >
              {{ field.label }}
            </el-checkbox>
          </el-checkbox-group>
          <div class="match-actions">
            <el-button
              type="primary"
              plain
              :disabled="matchSelectedFields.length === 0"
              :loading="templateDownloading"
              @click="downloadTemplate"
            >
              导出空模板
            </el-button>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-title">导入校验</div>
          <div class="file-row">
            <input
              ref="matchFileInput"
              class="file-input"
              type="file"
              accept=".xlsx"
              @change="handleMatchFileChange"
            />
            <el-button plain @click="chooseMatchFile">选择文件</el-button>
            <span class="file-name muted">{{ matchFile ? matchFile.name : '未选择文件' }}</span>
            <el-button v-if="matchFile" plain size="small" @click="clearMatchFile">x</el-button>
            <el-button
              type="primary"
              :disabled="!matchFile || matchSelectedFields.length === 0"
              :loading="previewLoading"
              @click="previewMatch"
            >
              校验
            </el-button>
          </div>
          <div
            v-if="matchPreview"
            class="match-result"
            :class="{ 'match-result--success': matchPreview.errors.length === 0 }"
          >
            <div class="match-result__header">
              <strong>
                {{
                  matchPreview.errors.length === 0
                    ? '校验通过，可以确认导入'
                    : '校验未通过'
                }}
              </strong>
              <span v-if="matchPreview.errors.length">
                错误数量：{{ matchPreview.errors.length }}
              </span>
              <span v-else>命中 {{ matchPreview.matchedOrderCount }} 个订单</span>
            </div>
            <div v-if="matchPreview.errors.length === 0" class="match-result__content">
              <div class="match-result__row">
                <span class="match-result__label">命中订单</span>
                <div class="match-tags">
                  <el-tag
                    v-for="orderId in displayedMatchedOrderIds"
                    :key="orderId"
                    size="small"
                    effect="plain"
                  >
                    {{ orderId }}
                  </el-tag>
                  <span v-if="hiddenMatchedOrderCount > 0" class="muted">
                    等 {{ hiddenMatchedOrderCount }} 个订单
                  </span>
                  <span v-if="matchPreview.matchedOrderIds.length === 0" class="muted">-</span>
                </div>
              </div>
              <div class="match-result__row">
                <span class="match-result__label">更新字段</span>
                <div class="match-tags">
                  <el-tag
                    v-for="field in matchPreview.updateFields"
                    :key="field"
                    size="small"
                    type="info"
                    effect="plain"
                  >
                    {{ field }}
                  </el-tag>
                  <span v-if="matchPreview.updateFields.length === 0" class="muted">-</span>
                </div>
              </div>
              <div v-if="postalCodeSelected" class="postal-pass-tip">
                邮编校验通过，空值将清空原邮编
              </div>
            </div>
          </div>
          <el-table v-if="matchPreview?.errors.length" :data="matchPreview.errors" size="small">
            <el-table-column label="行号" prop="row" width="80" />
            <el-table-column label="字段" prop="field" width="140" />
            <el-table-column label="原因" prop="message" min-width="260" show-overflow-tooltip />
          </el-table>
        </div>
      </div>
      <template #footer>
        <el-button @click="matchDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!canApplyMatch"
          :loading="applyLoading"
          @click="applyMatch"
        >
          确认导入
        </el-button>
      </template>
    </el-dialog>
  </PageSectionCard>
</template>

<script setup lang="ts">
import { getCountryOptions, type CountryOption } from '@/api/config'
import {
  applyOrderInfoMatch,
  downloadOrderInfoMatchTemplate,
  getOrderDetail,
  listDataShops,
  listOrderPlatforms,
  listOrders,
  previewOrderInfoMatch,
  updateOrderDetail,
  type DataOrderDetail,
  type DataOrderPatch,
  type DataOrderSummary,
  type OrderInfoMatchPreview
} from '@/api/data'
import MobileRecordList from '@/components/MobileRecordList.vue'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useResponsive } from '@/composables/useResponsive'
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS, formatCountryCodeForDisplay } from '@/utils/countries'
import { triggerBlobDownload } from '@/utils/download'
import type { TagType } from '@/utils/element'
import { formatDateTime } from '@/utils/format'
import { normalizeSortOrder, type SortChangeEvent, type SortState } from '@/utils/tableSort'
import { ElMessage } from 'element-plus'
import { SlidersHorizontal } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

const packageStatusOptions = [
  { label: '待审核', value: 'to_audit' },
  { label: '待处理', value: 'to_process' },
  { label: '申请运单号', value: 'apply_track_no' },
  { label: '待打印', value: 'to_print' },
  { label: '已发货', value: 'has_shipped' },
  { label: '已作废', value: 'has_canceled' }
]

const matchFields = [
  { key: 'country_code', label: '国家' },
  { key: 'postal_code', label: '邮编' }
]
const DEFAULT_MATCH_FIELDS = ['country_code', 'postal_code']

const rows = ref<DataOrderSummary[]>([])
const { isMobile } = useResponsive()
const auth = useAuthStore()
const canEdit = computed(() => auth.hasPermission('data_biz:edit'))
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const shopOptions = ref<Array<{ id: string; name: string }>>([])
const platformOptions = ref<string[]>([])
const countryOptions = ref<CountryOption[]>(
  COUNTRY_OPTIONS.map((option) => ({
    ...option,
    builtin: true,
    observed: false,
    can_be_eu_member: !['EU', 'ZZ'].includes(option.code)
  }))
)
const loading = ref(false)
const sortState = ref<SortState>({ prop: 'purchaseDate', order: 'desc' })
const dateRange = ref<[string, string] | null>(null)
const mobileFilterDrawerVisible = ref(false)
const filters = reactive({
  country: '',
  platform: '',
  status: '',
  sku: '',
  shop: ''
})

const dialogVisible = ref(false)
const detail = ref<DataOrderDetail | null>(null)
const editDialogVisible = ref(false)
const editDetail = ref<DataOrderDetail | null>(null)
const editSaving = ref(false)
const editForm = reactive({
  countryCode: '',
  postalCode: ''
})
type EditFormSnapshot = typeof editForm
const editOriginalSnapshot = ref<EditFormSnapshot | null>(null)

const matchDialogVisible = ref(false)
const matchSelectedFields = ref<string[]>([...DEFAULT_MATCH_FIELDS])
const matchFile = ref<File | null>(null)
const matchFileInput = ref<HTMLInputElement | null>(null)
const matchPreview = ref<OrderInfoMatchPreview | null>(null)
const templateDownloading = ref(false)
const previewLoading = ref(false)
const applyLoading = ref(false)
const canApplyMatch = computed(
  () => !!matchFile.value && !!matchPreview.value && matchPreview.value.errors.length === 0
)
const postalCodeSelected = computed(() => matchSelectedFields.value.includes('postal_code'))
const displayedMatchedOrderIds = computed(
  () => matchPreview.value?.matchedOrderIds.slice(0, 8) ?? []
)
const hiddenMatchedOrderCount = computed(() =>
  Math.max(
    (matchPreview.value?.matchedOrderIds.length ?? 0) - displayedMatchedOrderIds.value.length,
    0
  )
)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

let detailReqId = 0
let editReqId = 0
let listReqId = 0
let skuReloadTimer: ReturnType<typeof setTimeout> | null = null

function clearSkuReloadTimer(): void {
  if (skuReloadTimer !== null) {
    clearTimeout(skuReloadTimer)
    skuReloadTimer = null
  }
}

async function reload(): Promise<void> {
  clearSkuReloadTimer()
  const myReqId = ++listReqId
  loading.value = true
  try {
    const resp = await listOrders({
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      country: filters.country || undefined,
      shop_id: filters.shop || undefined,
      platform: filters.platform || undefined,
      status: filters.status || undefined,
      sku: filters.sku || undefined,
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortState.value.prop,
      sort_order: sortState.value.order
    })
    if (myReqId !== listReqId) return
    rows.value = resp.items
    total.value = resp.total
  } catch (err) {
    if (myReqId === listReqId) {
      ElMessage.error(getActionErrorMessage(err, '加载失败'))
    }
  } finally {
    if (myReqId === listReqId) {
      loading.value = false
    }
  }
}

async function loadShopOptions(): Promise<void> {
  try {
    const resp = await listDataShops()
    shopOptions.value = resp.items
      .map((item) => ({ id: item.id, name: item.name || item.id }))
      .sort((a, b) => a.name.localeCompare(b.name))
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载店铺列表失败'))
  }
}

async function loadPlatformOptions(): Promise<void> {
  try {
    platformOptions.value = await listOrderPlatforms()
  } catch {
    platformOptions.value = []
  }
}

async function loadCountryOptions(): Promise<void> {
  try {
    const resp = await getCountryOptions()
    countryOptions.value = resp.items
  } catch {
    // Keep builtin country options as fallback.
  }
}

function reloadFirstPage(): void {
  clearSkuReloadTimer()
  page.value = 1
  void reload()
}

function scheduleSkuReload(): void {
  page.value = 1
  clearSkuReloadTimer()
  skuReloadTimer = setTimeout(() => {
    skuReloadTimer = null
    void reload()
  }, 300)
}

async function openDetail(row: DataOrderSummary): Promise<void> {
  const myReqId = ++detailReqId
  dialogVisible.value = true
  detail.value = null
  try {
    const data = await getOrderDetail(row.shopId, row.amazonOrderId, row.packageSn)
    if (myReqId === detailReqId && dialogVisible.value) {
      detail.value = data
    }
  } catch (err) {
    if (myReqId === detailReqId) {
      dialogVisible.value = false
      ElMessage.error(getActionErrorMessage(err, '获取订单详情失败'))
    }
  }
}

async function openEdit(row: DataOrderSummary): Promise<void> {
  if (!canEdit.value) return
  const myReqId = ++editReqId
  editDialogVisible.value = true
  editDetail.value = null
  try {
    const data = await getOrderDetail(row.shopId, row.amazonOrderId, row.packageSn)
    if (myReqId === editReqId && editDialogVisible.value) {
      editDetail.value = data
      fillEditForm(data)
    }
  } catch (err) {
    if (myReqId === editReqId) {
      editDialogVisible.value = false
      ElMessage.error(getActionErrorMessage(err, '获取订单详情失败'))
    }
  }
}

function fillEditForm(data: DataOrderDetail): void {
  Object.assign(editForm, buildEditSnapshot(data))
  editOriginalSnapshot.value = { ...editForm }
}

function buildEditSnapshot(data: DataOrderDetail): EditFormSnapshot {
  return {
    countryCode: data.countryCode || '',
    postalCode: data.postalCode || ''
  }
}

async function saveEdit(): Promise<void> {
  if (!editDetail.value) return
  const payload = buildChangedEditPayload()
  if (Object.keys(payload).length === 0) {
    ElMessage.info('没有修改内容')
    return
  }
  editSaving.value = true
  try {
    await updateOrderDetail(
      editDetail.value.shopId,
      editDetail.value.amazonOrderId,
      editDetail.value.packageSn,
      payload
    )
    ElMessage.success('订单已更新')
    editDialogVisible.value = false
    await loadCountryOptions()
    await reload()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '保存失败'))
  } finally {
    editSaving.value = false
  }
}

function buildChangedEditPayload(): DataOrderPatch {
  const original = editOriginalSnapshot.value
  if (!original) return {}
  const fieldMap = {
    countryCode: 'countryCode',
    postalCode: 'postalCode'
  } as const
  const payload: DataOrderPatch = {}
  for (const key of Object.keys(fieldMap) as Array<keyof typeof fieldMap>) {
    if (editForm[key] !== original[key]) {
      payload[fieldMap[key]] = editForm[key]
    }
  }
  return payload
}

function displayPurchaseDate(order: DataOrderSummary | DataOrderDetail): string | null {
  return order.purchaseDateLocal ?? order.purchaseDate
}

function displayLastUpdateDate(order: DataOrderDetail): string | null {
  return order.lastUpdateDateLocal ?? order.lastUpdateDate
}

function formatOrderDisplayTime(value?: string | null): string {
  if (!value) return formatDateTime(value)
  const match = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/.exec(value)
  return match ? `${match[1]} ${match[2]}` : formatDateTime(value)
}

function openMatchDialog(): void {
  matchDialogVisible.value = true
}

async function downloadTemplate(): Promise<void> {
  templateDownloading.value = true
  try {
    const blob = await downloadOrderInfoMatchTemplate(matchSelectedFields.value)
    triggerBlobDownload(blob, '订单信息匹配模板.xlsx')
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '模板导出失败'))
  } finally {
    templateDownloading.value = false
  }
}

function handleMatchFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = input.files
  matchFile.value = files?.[0] || null
  matchPreview.value = null
  input.value = ''
}

function chooseMatchFile(): void {
  matchFileInput.value?.click()
}

function clearMatchFile(): void {
  matchFile.value = null
  matchPreview.value = null
  if (matchFileInput.value) {
    matchFileInput.value.value = ''
  }
}

function resetMatchSession(): void {
  clearMatchFile()
}

async function previewMatch(): Promise<void> {
  if (!matchFile.value) return
  previewLoading.value = true
  try {
    matchPreview.value = await previewOrderInfoMatch(matchFile.value, matchSelectedFields.value)
  } catch (err) {
    matchPreview.value = null
    ElMessage.error(getActionErrorMessage(err, '校验失败'))
  } finally {
    previewLoading.value = false
  }
}

async function applyMatch(): Promise<void> {
  if (!matchFile.value) return
  applyLoading.value = true
  try {
    const resp = await applyOrderInfoMatch(matchFile.value, matchSelectedFields.value)
    ElMessage.success(`已更新 ${resp.updatedOrderCount} 条订单`)
    matchDialogVisible.value = false
    await loadCountryOptions()
    await reload()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '导入失败'))
  } finally {
    applyLoading.value = false
  }
}

function statusType(status: string): TagType {
  return (
    (
      {
        has_shipped: 'success',
        has_canceled: 'danger',
        to_audit: 'warning',
        to_process: 'warning',
        apply_track_no: 'info',
        to_print: 'warning',
        Shipped: 'success',
        PartiallyShipped: 'success',
        Unshipped: 'warning',
        Pending: 'info',
        Canceled: 'danger',
        Unknown: 'info'
      } as Record<string, TagType>
    )[status] || 'info'
  )
}

const ORDER_STATUS_LABEL: Record<string, string> = {
  has_shipped: '已发货',
  has_canceled: '已作废',
  to_audit: '待审核',
  to_process: '待处理',
  apply_track_no: '申请运单号',
  to_print: '待打印',
  Shipped: '已发货',
  PartiallyShipped: '部分发货',
  Unshipped: '未发货',
  Pending: '待处理',
  Canceled: '已取消',
  Unknown: '未知'
}

function statusLabel(status: string): string {
  return ORDER_STATUS_LABEL[status] || status
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value =
    normalizedOrder && prop
      ? { prop, order: normalizedOrder }
      : { prop: 'purchaseDate', order: 'desc' }
  reloadFirstPage()
}

function handlePageChange(value: number): void {
  page.value = value
  void reload()
}

function handlePageSizeChange(value: number): void {
  pageSize.value = value
  page.value = 1
  void reload()
}

function goMobilePage(value: number): void {
  if (value < 1 || value > totalPages.value || value === page.value) return
  handlePageChange(value)
}

function resetMobileFilters(): void {
  clearSkuReloadTimer()
  dateRange.value = null
  Object.assign(filters, {
    country: '',
    platform: '',
    status: '',
    sku: '',
    shop: ''
  })
  page.value = 1
  void reload()
}

onMounted(() => {
  void loadCountryOptions()
  void loadShopOptions()
  void loadPlatformOptions()
  void reload()
})

watch(
  matchSelectedFields,
  () => {
    matchPreview.value = null
  },
  { deep: true }
)

onBeforeUnmount(() => {
  clearSkuReloadTimer()
})
</script>

<style lang="scss" scoped>
.order-filters {
  display: flex;
  align-items: center;
  gap: $space-3;
  flex-wrap: wrap;
}

.mobile-order-actions {
  display: none;
}

.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}

.nowrap {
  white-space: nowrap;
}

.detail-body,
.match-body {
  display: flex;
  flex-direction: column;
  gap: $space-5;
}

.section-title {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-weight: $font-weight-semibold;
  text-transform: uppercase;
  letter-spacing: $tracking-wider;
  margin-bottom: $space-3;
}

.kv-grid,
.edit-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $space-3;
}

.kv-grid > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: $space-2 $space-3;
  background: $color-bg-subtle;
  border-radius: $radius-md;
}

.label {
  font-size: 11px;
  color: $color-text-secondary;
  text-transform: uppercase;
  letter-spacing: $tracking-wider;
  font-weight: $font-weight-semibold;
}

.detail-items-table {
  width: 100%;
  border-collapse: collapse;
  font-size: $font-size-sm;
}

.detail-items-table th,
.detail-items-table td {
  padding: $space-2;
  border-bottom: 1px solid $color-border-subtle;
  text-align: left;
}

.align-right {
  text-align: right;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: $space-2 $space-3;
}

.match-actions,
.file-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: $space-3;
  margin-top: $space-3;
}

.match-result {
  display: flex;
  flex-direction: column;
  gap: $space-3;
  margin-top: $space-3;
  padding: $space-3;
  border: 1px solid $color-border-subtle;
  border-radius: $radius-md;
  background: $color-bg-subtle;
}

.match-result--success {
  border-color: var(--el-color-success-light-5);
  background: var(--el-color-success-light-9);
}

.match-result__header,
.match-result__row,
.match-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: $space-2;
}

.match-result__header {
  justify-content: space-between;
  color: $color-text-primary;
}

.match-result__content {
  display: flex;
  flex-direction: column;
  gap: $space-2;
}

.match-result__label {
  flex: 0 0 64px;
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.postal-pass-tip {
  color: var(--el-color-success);
  font-size: $font-size-sm;
}

.file-input {
  display: none;
}

.file-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .order-filters {
    width: 100%;
  }
}

@media (max-width: 767px) {
  .desktop-order-filters {
    display: none;
  }

  .mobile-order-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    width: 100%;
    gap: $space-2;
    align-items: stretch;

    :deep(.el-input),
    :deep(.el-button) {
      height: 32px;
    }
  }

  .mobile-order-search {
    min-width: 0;
  }

  .mobile-filter-trigger {
    display: inline-flex;
    align-items: center;
    gap: $space-1;
  }

  .mobile-match-action {
    grid-column: 1 / -1;
    width: 100%;
  }

  .mobile-filter-form {
    display: flex;
    flex-direction: column;
    gap: $space-4;
  }

  .mobile-filter-field {
    display: flex;
    flex-direction: column;
    gap: $space-2;
    color: $color-text-primary;
    font-size: $font-size-sm;
    font-weight: $font-weight-medium;

    :deep(.el-select),
    :deep(.el-input),
    :deep(.el-date-editor) {
      width: 100% !important;
    }
  }

  .mobile-filter-footer {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: $space-2;
    width: 100%;
  }

  .mobile-orders-list {
    padding-bottom: calc(68px + env(safe-area-inset-bottom));
  }

  .mobile-fixed-pagination {
    position: fixed;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 20;
    display: grid;
    grid-template-columns: 82px minmax(0, 1fr) 82px;
    align-items: center;
    gap: $space-2;
    padding: $space-3 $space-4 calc($space-3 + env(safe-area-inset-bottom));
    border-top: 1px solid $color-border-subtle;
    background: rgba($color-bg-card, 0.96);
    box-shadow: 0 -8px 24px rgba(15, 23, 42, 0.08);
    backdrop-filter: blur(10px);

    :deep(.el-button) {
      width: 100%;
      margin: 0;
    }
  }

  .mobile-page-indicator {
    min-width: 0;
    overflow: hidden;
    color: $color-text-primary;
    font-size: $font-size-sm;
    font-weight: $font-weight-semibold;
    text-align: center;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-order-card {
    display: flex;
    flex-direction: column;
    gap: $space-3;
  }

  .mobile-card-head,
  .mobile-card-meta,
  .mobile-card-actions {
    display: flex;
    align-items: center;
    gap: $space-2;
  }

  .mobile-card-head {
    justify-content: space-between;
  }

  .mobile-card-title {
    min-width: 0;
    overflow: hidden;
    color: $color-text-primary;
    font-weight: $font-weight-semibold;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-card-meta {
    flex-wrap: wrap;
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }

  .mobile-kv-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: $space-2;
  }

  .mobile-kv-grid > div {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    padding: $space-2;
    border-radius: $radius-md;
    background: $color-bg-subtle;
  }

  .mobile-kv-grid span {
    color: $color-text-secondary;
    font-size: 11px;
  }

  .mobile-kv-grid strong {
    min-width: 0;
    overflow: hidden;
    font-size: $font-size-xs;
    font-weight: $font-weight-medium;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-kv-grid__wide {
    grid-column: 1 / -1;
  }

  .mobile-card-actions {
    justify-content: flex-end;
  }

  .kv-grid,
  .edit-form,
  .field-grid {
    grid-template-columns: 1fr;
  }

  :global(.order-detail-dialog.is-fullscreen),
  :global(.order-match-dialog.is-fullscreen) {
    display: flex;
    flex-direction: column;
  }

  :global(.order-detail-dialog.is-fullscreen .el-dialog__body),
  :global(.order-match-dialog.is-fullscreen .el-dialog__body) {
    flex: 1;
    max-height: none;
  }
}
</style>
