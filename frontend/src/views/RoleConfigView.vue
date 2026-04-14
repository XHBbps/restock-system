<template>
  <PageSectionCard title="角色配置">
    <template #actions>
      <el-button
        v-if="auth.hasPermission('auth:manage')"
        type="primary"
        @click="openCreate"
      >
        新建角色
      </el-button>
    </template>

    <el-table v-loading="loading" :data="roles" stripe table-layout="fixed" empty-text="暂无角色数据">
      <el-table-column prop="name" label="角色名称" min-width="120" />
      <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
      <el-table-column label="类型" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.is_superadmin" type="warning" size="small">系统内置</el-tag>
          <el-tag v-else size="small">自定义</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="user_count" label="用户数" width="90" align="center" />
      <el-table-column
        v-if="auth.hasPermission('auth:manage')"
        label="操作"
        width="160"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-tooltip
            :disabled="canDelete(row)"
            :content="deleteDisabledReason(row)"
            placement="top"
          >
            <span>
              <el-button
                link
                type="danger"
                size="small"
                :disabled="!canDelete(row)"
                @click="handleDelete(row)"
              >
                删除
              </el-button>
            </span>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新建角色' : '编辑角色'"
      width="720px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form :model="form" label-width="80px" style="max-width: 600px">
        <el-form-item label="角色名称" required>
          <el-input
            v-model="form.name"
            maxlength="50"
            show-word-limit
            placeholder="请输入角色名称"
            :disabled="editingRole?.is_superadmin"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            maxlength="200"
            show-word-limit
            placeholder="可选描述"
            :disabled="editingRole?.is_superadmin"
          />
        </el-form-item>
      </el-form>

      <div class="permission-section">
        <div class="permission-section-title">权限配置</div>

        <el-alert
          v-if="editingRole?.is_superadmin"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        >
          超管角色自动拥有所有权限，权限不可修改
        </el-alert>

        <div v-loading="permLoading" class="permission-groups" style="max-height: 60vh; overflow-y: auto">
          <div
            v-for="(perms, groupName) in permissionGroups"
            :key="groupName"
            class="permission-group-card"
          >
            <div class="group-header">
              <el-checkbox
                :model-value="isGroupAllChecked(perms)"
                :indeterminate="isGroupIndeterminate(perms)"
                :disabled="!!editingRole?.is_superadmin"
                @change="(val) => toggleGroup(perms, !!val)"
              >
                {{ groupName }}
              </el-checkbox>
            </div>
            <div class="group-body">
              <el-checkbox
                v-for="p in perms"
                :key="p.code"
                :model-value="checkedCodes.has(p.code)"
                :disabled="!!editingRole?.is_superadmin"
                @change="(val) => toggleCode(p.code, !!val)"
              >
                {{ p.name }}
              </el-checkbox>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="!!editingRole?.is_superadmin"
          @click="handleSave"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </PageSectionCard>
</template>

<script setup lang="ts">
import {
  createRole,
  deleteRole,
  getPermissions,
  getRolePermissions,
  getRoles,
  updateRole,
  updateRolePermissions,
  type PermissionOut,
  type RoleOut,
} from '@/api/auth-management'
import PageSectionCard from '@/components/PageSectionCard.vue'
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

const auth = useAuthStore()

// ── Table data ──
const roles = ref<RoleOut[]>([])
const permissions = ref<PermissionOut[]>([])
const loading = ref(false)

// ── Dialog state ──
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingRole = ref<RoleOut | null>(null)
const form = reactive({ name: '', description: '' })
const checkedCodes = ref<Set<string>>(new Set())
const saving = ref(false)
const permLoading = ref(false)

// ── Grouped permissions ──
const permissionGroups = computed(() => {
  const groups: Record<string, PermissionOut[]> = {}
  for (const p of permissions.value) {
    if (!groups[p.group_name]) groups[p.group_name] = []
    groups[p.group_name].push(p)
  }
  return groups
})

// ── Permission helpers ──
function isGroupAllChecked(perms: PermissionOut[]): boolean {
  return perms.length > 0 && perms.every((p) => checkedCodes.value.has(p.code))
}

function isGroupIndeterminate(perms: PermissionOut[]): boolean {
  const checked = perms.filter((p) => checkedCodes.value.has(p.code)).length
  return checked > 0 && checked < perms.length
}

function toggleGroup(perms: PermissionOut[], val: boolean): void {
  const next = new Set(checkedCodes.value)
  for (const p of perms) {
    if (val) next.add(p.code)
    else next.delete(p.code)
  }
  checkedCodes.value = next
}

function toggleCode(code: string, val: boolean): void {
  const next = new Set(checkedCodes.value)
  if (val) next.add(code)
  else next.delete(code)
  checkedCodes.value = next
}

// ── Delete helpers ──
function canDelete(row: RoleOut): boolean {
  return !row.is_superadmin && row.user_count === 0
}

function deleteDisabledReason(row: RoleOut): string {
  if (row.is_superadmin) return '系统内置角色不可删除'
  if (row.user_count > 0) return '该角色下还有用户，无法删除'
  return ''
}

// ── Load data ──
async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [rolesData, permsData] = await Promise.all([getRoles(), getPermissions()])
    roles.value = rolesData
    permissions.value = permsData
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载角色数据失败'))
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

// ── Dialog actions ──
function openCreate(): void {
  dialogMode.value = 'create'
  editingRole.value = null
  form.name = ''
  form.description = ''
  checkedCodes.value = new Set()
  dialogVisible.value = true
}

async function openEdit(role: RoleOut): Promise<void> {
  dialogMode.value = 'edit'
  editingRole.value = role
  form.name = role.name
  form.description = role.description

  if (role.is_superadmin) {
    checkedCodes.value = new Set(permissions.value.map((p) => p.code))
  } else {
    permLoading.value = true
    try {
      const codes = await getRolePermissions(role.id)
      checkedCodes.value = new Set(codes)
    } catch (err) {
      ElMessage.error(getActionErrorMessage(err, '加载角色权限失败'))
    } finally {
      permLoading.value = false
    }
  }

  dialogVisible.value = true
}

async function handleSave(): Promise<void> {
  if (!form.name.trim()) {
    ElMessage.warning('请输入角色名称')
    return
  }

  saving.value = true
  try {
    if (dialogMode.value === 'create') {
      const newRole = await createRole({ name: form.name, description: form.description })
      if (checkedCodes.value.size > 0) {
        await updateRolePermissions(newRole.id, [...checkedCodes.value])
      }
      ElMessage.success('角色创建成功')
    } else if (editingRole.value && !editingRole.value.is_superadmin) {
      await updateRole(editingRole.value.id, { name: form.name, description: form.description })
      await updateRolePermissions(editingRole.value.id, [...checkedCodes.value])
      ElMessage.success('角色更新成功')
    }
    dialogVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '操作失败'))
  } finally {
    saving.value = false
  }
}

async function handleDelete(role: RoleOut): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除角色「${role.name}」吗？此操作不可撤销。`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return // user cancelled
  }

  try {
    await deleteRole(role.id)
    ElMessage.success('角色已删除')
    await loadData()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '删除失败'))
  }
}
</script>

<style lang="scss" scoped>
.permission-section {
  margin-top: $space-4;
}

.permission-section-title {
  font-size: $font-size-sm;
  font-weight: $font-weight-semibold;
  margin-bottom: $space-3;
  color: $color-text-primary;
}

.permission-groups {
  display: flex;
  flex-direction: column;
  gap: $space-3;
}

.permission-group-card {
  border: 1px solid $color-border-default;
  border-radius: 6px;
  overflow: hidden;
}

.group-header {
  padding: 8px 12px;
  background: $color-bg-subtle;
  border-bottom: 1px solid $color-border-default;
  font-weight: 500;
}

.group-body {
  padding: 12px 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
}
</style>
