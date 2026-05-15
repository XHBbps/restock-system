<template>
  <div class="third-party-inventory-view">
    <PageSectionCard title="三方仓库存导入" description="预览不会影响当前库存；确认后会整批替换当前三方仓库存。">
      <template #actions>
        <el-upload :auto-upload="false" :show-file-list="false" accept=".xlsx,.xls" :on-change="onFileChange">
          <el-button>选择 Excel</el-button>
        </el-upload>
        <el-button type="primary" :disabled="!selectedFile" :loading="previewing" @click="previewImport">预览导入</el-button>
        <el-button v-if="previewBatch" type="success" :loading="confirming" @click="confirmImport">确认整批替换</el-button>
        <el-button v-if="previewBatch" @click="cancelPreview">取消预览</el-button>
      </template>

      <div v-if="selectedFile" class="selected-file">已选择：{{ selectedFile.name }}</div>
      <div v-if="previewBatch" class="preview-panel">
        <div class="stat-grid">
          <div><span>总行数</span><strong>{{ previewBatch.rowCount }}</strong></div>
          <div><span>有效行</span><strong>{{ previewBatch.validRowCount }}</strong></div>
          <div><span>跳过行</span><strong>{{ previewBatch.skippedRowCount }}</strong></div>
          <div><span>新仓库</span><strong>{{ previewBatch.newWarehouseCount }}</strong></div>
          <div><span>未维护国家</span><strong>{{ previewBatch.unmaintainedWarehouseCount }}</strong></div>
          <div><span>问题行</span><strong>{{ previewBatch.issues.length }}</strong></div>
        </div>
        <el-alert title="确认导入会删除并重建当前三方仓库存，不会修改导入历史。" type="warning" :closable="false" />
        <div v-if="previewBatch.newWarehouses.length" class="tag-row">
          <span>新三方仓</span>
          <el-tag v-for="name in previewBatch.newWarehouses" :key="name" type="info">{{ name }}</el-tag>
        </div>
        <div v-if="previewBatch.unmaintainedWarehouses.length" class="tag-row">
          <span>未维护国家</span>
          <el-tag v-for="name in previewBatch.unmaintainedWarehouses" :key="name" type="warning">{{ name }}</el-tag>
        </div>
        <el-table v-if="previewBatch.issues.length" :data="previewBatch.issues" size="small">
          <el-table-column label="行号" prop="row" width="80" />
          <el-table-column label="仓库" prop="warehouseName" min-width="160" />
          <el-table-column label="SKU" prop="commoditySku" min-width="160" />
          <el-table-column label="问题" prop="message" min-width="260" />
        </el-table>
      </div>

      <el-divider />
      <el-table v-loading="historyLoading" :data="batches" row-key="id" empty-text="暂无导入历史">
        <el-table-column label="批次" prop="id" width="90" />
        <el-table-column label="文件名" prop="filename" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="batchStatusType(row.status)" size="small">{{ batchStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="有效/总行" width="120">
          <template #default="{ row }">{{ row.validRowCount }} / {{ row.rowCount }}</template>
        </el-table-column>
        <el-table-column label="导入人" prop="createdBy" width="120" />
        <el-table-column label="导入时间" width="168">
          <template #default="{ row }"><span class="muted mono">{{ formatUpdateTime(row.createdAt) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openBatchDetail(row.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <TablePaginationBar
        v-model:current-page="historyPage"
        v-model:page-size="historyPageSize"
        :total="historyTotal"
        :page-sizes="[10, 20, 50]"
        @current-change="handleHistoryPageChange"
        @size-change="handleHistorySizeChange"
      />
    </PageSectionCard>

    <PageSectionCard title="当前三方仓库存" description="手工新增、编辑、删除只影响当前库存，不回写导入历史。">
      <template #actions>
        <el-input v-model="filters.warehouse_keyword" placeholder="搜索三方仓" clearable style="width: 160px" @keyup.enter="reloadInventory(true)" />
        <el-input v-model="filters.sku" placeholder="搜索 SKU" clearable style="width: 160px" @keyup.enter="reloadInventory(true)" />
        <el-select v-model="filters.country" placeholder="国家" clearable filterable style="width: 130px" @change="reloadInventory(true)">
          <el-option v-for="option in countryOptions" :key="option.code" :label="option.label" :value="option.code" />
        </el-select>
        <el-checkbox v-model="filters.only_missing_country" @change="reloadInventory(true)">未维护国家</el-checkbox>
        <el-checkbox v-model="filters.only_participating" @change="reloadInventory(true)">参与计算</el-checkbox>
        <el-checkbox v-model="filters.only_nonzero" @change="reloadInventory(true)">非零库存</el-checkbox>
        <el-button v-if="auth.hasPermission('data_biz:edit')" type="primary" @click="openItemCreate">新增库存</el-button>
      </template>

      <el-table v-loading="inventoryLoading" :data="warehouseGroups" row-key="warehouseId" empty-text="暂无三方仓库存">
        <el-table-column type="expand">
          <template #default="{ row }">
            <el-table :data="row.items" size="small">
              <el-table-column label="SKU" prop="commoditySku" min-width="180" />
              <el-table-column label="可用数" prop="available" width="100" align="right" />
              <el-table-column label="占用数" prop="reserved" width="100" align="right" />
              <el-table-column label="来源批次" width="100">
                <template #default="{ row: item }">{{ item.sourceBatchId || '-' }}</template>
              </el-table-column>
              <el-table-column label="更新时间" width="168">
                <template #default="{ row: item }"><span class="muted mono">{{ formatUpdateTime(item.updatedAt) }}</span></template>
              </el-table-column>
              <el-table-column v-if="auth.hasPermission('data_biz:edit')" label="操作" width="140">
                <template #default="{ row: item }">
                  <el-button link type="primary" @click="openItemEdit(item)">编辑</el-button>
                  <el-button link type="danger" @click="removeItem(item)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-table-column>
        <el-table-column label="三方仓" prop="warehouseName" min-width="220" />
        <el-table-column label="国家" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.country" size="small">{{ row.country }}</el-tag>
            <el-tag v-else type="warning" size="small">未维护</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="参与计算" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.participates ? 'success' : 'info'" size="small">{{ row.participates ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="SKU 数" prop="skuCount" width="100" align="right" />
        <el-table-column label="可用合计" prop="totalAvailable" width="120" align="right" />
        <el-table-column label="占用合计" prop="totalReserved" width="120" align="right" />
      </el-table>
      <TablePaginationBar
        v-model:current-page="inventoryPage"
        v-model:page-size="inventoryPageSize"
        :total="inventoryTotal"
        :page-sizes="[10, 20, 50]"
        @current-change="handleInventoryPageChange"
        @size-change="handleInventorySizeChange"
      />
    </PageSectionCard>

    <el-dialog v-model="itemDialogVisible" :title="editingItem ? '编辑三方库存' : '新增三方库存'" width="460px">
      <el-form label-width="84px">
        <el-form-item label="三方仓" required>
          <el-select v-model="itemForm.warehouseId" filterable style="width: 100%">
            <el-option v-for="warehouse in warehouseOptions" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="SKU" required>
          <el-input v-model="itemForm.commoditySku" />
        </el-form-item>
        <el-form-item label="可用数" required>
          <el-input-number v-model="itemForm.available" :min="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="占用数" required>
          <el-input-number v-model="itemForm.reserved" :min="0" :step="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="itemSaving" @click="saveItem">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="batchDetailVisible" title="导入批次详情" size="720px">
      <el-table v-loading="batchDetailLoading" :data="batchDetailRows" size="small" empty-text="暂无明细">
        <el-table-column label="行号" prop="sourceRowNo" width="80" />
        <el-table-column label="仓库" prop="warehouseNameRaw" min-width="150" />
        <el-table-column label="SKU" prop="commoditySku" min-width="150" />
        <el-table-column label="可用数" prop="available" width="90" align="right" />
        <el-table-column label="待出库" prop="reserved" width="90" align="right" />
        <el-table-column label="问题" prop="errorMessage" min-width="220" show-overflow-tooltip />
      </el-table>
      <TablePaginationBar
        v-model:current-page="batchDetailPage"
        v-model:page-size="batchDetailPageSize"
        :total="batchDetailTotal"
        :page-sizes="[20, 50, 100]"
        @current-change="handleBatchDetailPageChange"
        @size-change="handleBatchDetailSizeChange"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { getCountryOptions, type CountryOption } from '@/api/config'
import {
  cancelThirdPartyInventoryImport,
  confirmThirdPartyInventoryImport,
  createThirdPartyInventoryItem,
  deleteThirdPartyInventoryItem,
  getThirdPartyInventoryBatch,
  listThirdPartyInventoryBatches,
  listThirdPartyInventoryWarehouseGroups,
  listThirdPartyWarehouses,
  previewThirdPartyInventoryImport,
  updateThirdPartyInventoryItem,
  type ThirdPartyInventoryImportBatch,
  type ThirdPartyInventoryImportItem,
  type ThirdPartyInventoryItem,
  type ThirdPartyInventoryPreview,
  type ThirdPartyInventoryWarehouseGroup,
  type ThirdPartyWarehouse,
} from '@/api/data'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { formatUpdateTime } from '@/utils/format'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

const auth = useAuthStore()
const selectedFile = ref<File | null>(null)
const previewBatch = ref<ThirdPartyInventoryPreview | null>(null)
const previewing = ref(false)
const confirming = ref(false)

const batches = ref<ThirdPartyInventoryImportBatch[]>([])
const historyLoading = ref(false)
const historyPage = ref(1)
const historyPageSize = ref(10)
const historyTotal = ref(0)

const warehouseGroups = ref<ThirdPartyInventoryWarehouseGroup[]>([])
const inventoryLoading = ref(false)
const inventoryPage = ref(1)
const inventoryPageSize = ref(20)
const inventoryTotal = ref(0)
const filters = reactive({
  warehouse_keyword: '',
  sku: '',
  country: '',
  only_missing_country: false,
  only_participating: false,
  only_nonzero: false,
})

const warehouseOptions = ref<ThirdPartyWarehouse[]>([])
const itemDialogVisible = ref(false)
const itemSaving = ref(false)
const editingItem = ref<ThirdPartyInventoryItem | null>(null)
const itemForm = reactive({ warehouseId: undefined as number | undefined, commoditySku: '', available: 0, reserved: 0 })

const batchDetailVisible = ref(false)
const batchDetailLoading = ref(false)
const batchDetailId = ref<number | null>(null)
const batchDetailRows = ref<ThirdPartyInventoryImportItem[]>([])
const batchDetailPage = ref(1)
const batchDetailPageSize = ref(50)
const batchDetailTotal = ref(0)

const countryOptions = ref<CountryOption[]>(
  COUNTRY_OPTIONS.map((option) => ({ ...option, builtin: true, observed: false, can_be_eu_member: !['EU', 'ZZ'].includes(option.code) })),
)

function onFileChange(file: UploadFile): void {
  selectedFile.value = file.raw || null
  previewBatch.value = null
}

async function previewImport(): Promise<void> {
  if (!selectedFile.value) return
  previewing.value = true
  try {
    previewBatch.value = await previewThirdPartyInventoryImport(selectedFile.value)
    ElMessage.success('导入预览已生成')
    await reloadHistory(false)
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '预览失败'))
  } finally {
    previewing.value = false
  }
}

async function confirmImport(): Promise<void> {
  if (!previewBatch.value) return
  try {
    await ElMessageBox.confirm('确认后将整批替换当前三方仓库存。', '确认导入', { type: 'warning' })
  } catch {
    return
  }
  confirming.value = true
  try {
    await confirmThirdPartyInventoryImport(previewBatch.value.id)
    ElMessage.success('三方仓库存已替换')
    previewBatch.value = null
    selectedFile.value = null
    await Promise.all([reloadHistory(false), reloadInventory(false), loadWarehouseOptions()])
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '确认导入失败'))
  } finally {
    confirming.value = false
  }
}

async function cancelPreview(): Promise<void> {
  if (previewBatch.value) {
    try {
      await cancelThirdPartyInventoryImport(previewBatch.value.id)
      await reloadHistory(false)
    } catch {
      // ignore stale pending batch cancellation failures
    }
  }
  previewBatch.value = null
  selectedFile.value = null
}

async function reloadHistory(resetPage = false): Promise<void> {
  if (resetPage) historyPage.value = 1
  historyLoading.value = true
  try {
    const resp = await listThirdPartyInventoryBatches({ page: historyPage.value, page_size: historyPageSize.value })
    batches.value = resp.items
    historyTotal.value = resp.total
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载导入历史失败'))
  } finally {
    historyLoading.value = false
  }
}

async function reloadInventory(resetPage = false): Promise<void> {
  if (resetPage) inventoryPage.value = 1
  inventoryLoading.value = true
  try {
    const resp = await listThirdPartyInventoryWarehouseGroups({
      warehouse_keyword: filters.warehouse_keyword || undefined,
      sku: filters.sku || undefined,
      country: filters.country || undefined,
      only_missing_country: filters.only_missing_country,
      only_participating: filters.only_participating ? true : undefined,
      only_nonzero: filters.only_nonzero,
      page: inventoryPage.value,
      page_size: inventoryPageSize.value,
    })
    warehouseGroups.value = resp.items
    inventoryTotal.value = resp.total
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载当前库存失败'))
  } finally {
    inventoryLoading.value = false
  }
}

async function loadWarehouseOptions(): Promise<void> {
  try {
    warehouseOptions.value = (await listThirdPartyWarehouses({ page_size: 500 })).items
  } catch {
    warehouseOptions.value = []
  }
}

async function loadCountryOptions(): Promise<void> {
  try {
    countryOptions.value = (await getCountryOptions()).items
  } catch {
    // keep builtin fallback
  }
}

function openItemCreate(): void {
  editingItem.value = null
  itemForm.warehouseId = warehouseOptions.value[0]?.id
  itemForm.commoditySku = ''
  itemForm.available = 0
  itemForm.reserved = 0
  itemDialogVisible.value = true
}

function openItemEdit(item: ThirdPartyInventoryItem): void {
  editingItem.value = item
  itemForm.warehouseId = item.warehouseId
  itemForm.commoditySku = item.commoditySku
  itemForm.available = item.available
  itemForm.reserved = item.reserved
  itemDialogVisible.value = true
}

async function saveItem(): Promise<void> {
  if (!itemForm.warehouseId || !itemForm.commoditySku.trim()) {
    ElMessage.warning('请选择三方仓并填写 SKU')
    return
  }
  itemSaving.value = true
  try {
    const payload = {
      warehouseId: itemForm.warehouseId,
      commoditySku: itemForm.commoditySku.trim(),
      available: itemForm.available,
      reserved: itemForm.reserved,
    }
    if (editingItem.value) await updateThirdPartyInventoryItem(editingItem.value.id, payload)
    else await createThirdPartyInventoryItem(payload)
    ElMessage.success('库存已保存')
    itemDialogVisible.value = false
    await reloadInventory(false)
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '保存库存失败'))
  } finally {
    itemSaving.value = false
  }
}

async function removeItem(item: ThirdPartyInventoryItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除 SKU「${item.commoditySku}」？`, '删除确认', { type: 'warning' })
    await deleteThirdPartyInventoryItem(item.id)
    ElMessage.success('库存已删除')
    await reloadInventory(false)
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(getActionErrorMessage(err, '删除库存失败'))
  }
}

async function openBatchDetail(batchId: number): Promise<void> {
  batchDetailId.value = batchId
  batchDetailPage.value = 1
  batchDetailVisible.value = true
  await reloadBatchDetail()
}

async function reloadBatchDetail(): Promise<void> {
  if (!batchDetailId.value) return
  batchDetailLoading.value = true
  try {
    const resp = await getThirdPartyInventoryBatch(batchDetailId.value, {
      page: batchDetailPage.value,
      page_size: batchDetailPageSize.value,
    })
    batchDetailRows.value = resp.items
    batchDetailTotal.value = resp.itemTotal
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载批次详情失败'))
  } finally {
    batchDetailLoading.value = false
  }
}

function handleHistoryPageChange(value: number): void {
  historyPage.value = value
  void reloadHistory(false)
}

function handleHistorySizeChange(value: number): void {
  historyPageSize.value = value
  void reloadHistory(true)
}

function handleInventoryPageChange(value: number): void {
  inventoryPage.value = value
  void reloadInventory(false)
}

function handleInventorySizeChange(value: number): void {
  inventoryPageSize.value = value
  void reloadInventory(true)
}

function handleBatchDetailPageChange(value: number): void {
  batchDetailPage.value = value
  void reloadBatchDetail()
}

function handleBatchDetailSizeChange(value: number): void {
  batchDetailPageSize.value = value
  batchDetailPage.value = 1
  void reloadBatchDetail()
}

function batchStatusText(status: string): string {
  return ({ pending: '待确认', applied: '已应用', failed: '失败', expired: '已取消' } as Record<string, string>)[status] || status
}

function batchStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'applied') return 'success'
  if (status === 'pending') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

onMounted(() => {
  void loadCountryOptions()
  void loadWarehouseOptions()
  void reloadHistory()
  void reloadInventory()
})
</script>

<style lang="scss" scoped>
.third-party-inventory-view {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.selected-file,
.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}

.preview-panel {
  display: flex;
  flex-direction: column;
  gap: $space-3;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: $space-2;
}

.stat-grid > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: $space-2;
  border: 1px solid $color-border-default;
  border-radius: $radius-md;
}

.stat-grid span {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.stat-grid strong {
  font-size: $font-size-lg;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: $space-2;
}
</style>
