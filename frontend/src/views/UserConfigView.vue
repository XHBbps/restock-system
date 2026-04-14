<template>
  <PageSectionCard title="授权配置">
    <template #actions>
      <el-button
        v-if="auth.hasPermission('auth:manage')"
        type="primary"
        @click="openCreate"
      >
        新建用户
      </el-button>
    </template>

    <el-table v-loading="loading" :data="users" stripe table-layout="fixed" empty-text="暂无用户数据">
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="display_name" label="显示名" min-width="120" />
      <el-table-column label="角色" min-width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_superadmin ? 'warning' : undefined" size="small">
            {{ row.role_name }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '正常' : '已禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后登录" min-width="160">
        <template #default="{ row }">
          {{ row.last_login_at ? formatDateTime(row.last_login_at) : '-' }}
        </template>
      </el-table-column>
      <el-table-column
        v-if="auth.hasPermission('auth:manage')"
        label="操作"
        width="200"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-tooltip
            :disabled="canDisable(row)"
            :content="disableReason(row)"
            placement="top"
          >
            <span>
              <el-button
                link
                :type="row.is_active ? 'warning' : 'success'"
                size="small"
                :disabled="!canDisable(row)"
                @click="handleToggleStatus(row)"
              >
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
            </span>
          </el-tooltip>
          <el-dropdown trigger="click" @command="(cmd: string) => handleDropdownCommand(cmd, row)">
            <el-button link type="primary" size="small">更多</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="resetPassword">重置密码</el-dropdown-item>
                <el-dropdown-item
                  command="delete"
                  :disabled="!canDelete(row)"
                >
                  <span class="dropdown-danger-text">删除</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create User Dialog -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建用户"
      width="500px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form :model="createForm" label-width="80px" style="max-width: 400px">
        <el-form-item label="用户名" required>
          <el-input
            v-model="createForm.username"
            maxlength="50"
            show-word-limit
            placeholder="字母、数字、下划线"
          />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input
            v-model="createForm.display_name"
            maxlength="50"
            show-word-limit
            placeholder="可选"
          />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            maxlength="128"
            placeholder="至少 6 位"
          />
        </el-form-item>
        <el-form-item label="确认密码" required>
          <el-input
            v-model="createForm.confirmPassword"
            type="password"
            show-password
            maxlength="128"
            placeholder="再次输入密码"
          />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="createForm.role_id" placeholder="请选择角色" style="width: 100%">
            <el-option
              v-for="r in roles"
              :key="r.id"
              :label="r.name"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleCreate">保存</el-button>
      </template>
    </el-dialog>

    <!-- Edit User Dialog -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑用户"
      width="500px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form :model="editForm" label-width="80px" style="max-width: 400px">
        <el-form-item label="用户名">
          <el-input :model-value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input
            v-model="editForm.display_name"
            maxlength="50"
            show-word-limit
            placeholder="可选"
          />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="editForm.role_id" placeholder="请选择角色" style="width: 100%">
            <el-option
              v-for="r in roles"
              :key="r.id"
              :label="r.name"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleEditSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- Reset Password Dialog -->
    <el-dialog
      v-model="resetPwdDialogVisible"
      title="重置密码"
      width="500px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert
        :title="`将为用户 ${resetPwdTarget?.username ?? ''} 设置新密码`"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-form :model="resetPwdForm" label-width="80px" style="max-width: 400px">
        <el-form-item label="新密码" required>
          <el-input
            v-model="resetPwdForm.password"
            type="password"
            show-password
            maxlength="128"
            placeholder="至少 6 位"
          />
        </el-form-item>
        <el-form-item label="确认密码" required>
          <el-input
            v-model="resetPwdForm.confirmPassword"
            type="password"
            show-password
            maxlength="128"
            placeholder="再次输入密码"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleResetPassword">确认</el-button>
      </template>
    </el-dialog>
  </PageSectionCard>
</template>

<script setup lang="ts">
import {
  createUser,
  deleteUser,
  getRoles,
  getUsers,
  resetPassword,
  toggleUserStatus,
  updateUser,
  type RoleOut,
  type UserOut,
} from '@/api/auth-management'
import PageSectionCard from '@/components/PageSectionCard.vue'
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { formatDateTime } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

const auth = useAuthStore()

// ── Table data ──
const users = ref<UserOut[]>([])
const roles = ref<RoleOut[]>([])
const loading = ref(false)
const saving = ref(false)

// ── Boundary protection ──
const superadminCount = computed(() =>
  users.value.filter((u) => u.is_superadmin && u.is_active).length,
)

function canDisable(u: UserOut): boolean {
  if (u.id === auth.user?.id) return false
  if (u.is_superadmin && superadminCount.value <= 1) return false
  return true
}

function canDelete(u: UserOut): boolean {
  if (u.id === auth.user?.id) return false
  if (u.is_superadmin && superadminCount.value <= 1) return false
  return true
}

function disableReason(u: UserOut): string {
  if (u.id === auth.user?.id) return '不能操作自己的账户'
  if (u.is_superadmin && superadminCount.value <= 1) return '至少需要保留一个超管用户'
  return ''
}

function canChangeRole(u: UserOut, newRoleIsSuperadmin: boolean): boolean {
  if (u.is_superadmin && !newRoleIsSuperadmin && superadminCount.value <= 1) return false
  return true
}

// ── Load data ──
async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [usersData, rolesData] = await Promise.all([getUsers(), getRoles()])
    users.value = usersData
    roles.value = rolesData
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载用户数据失败'))
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

// ── Create Dialog ──
const createDialogVisible = ref(false)
const createForm = reactive({
  username: '',
  display_name: '',
  password: '',
  confirmPassword: '',
  role_id: undefined as number | undefined,
})

function openCreate(): void {
  createForm.username = ''
  createForm.display_name = ''
  createForm.password = ''
  createForm.confirmPassword = ''
  createForm.role_id = undefined
  createDialogVisible.value = true
}

async function handleCreate(): Promise<void> {
  if (!createForm.username.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!/^[\w]+$/.test(createForm.username)) {
    ElMessage.warning('用户名只能包含字母、数字和下划线')
    return
  }
  if (!createForm.password || createForm.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (createForm.password !== createForm.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  if (!createForm.role_id) {
    ElMessage.warning('请选择角色')
    return
  }

  saving.value = true
  try {
    await createUser({
      username: createForm.username,
      display_name: createForm.display_name,
      password: createForm.password,
      role_id: createForm.role_id,
    })
    ElMessage.success('用户创建成功')
    createDialogVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '创建用户失败'))
  } finally {
    saving.value = false
  }
}

// ── Edit Dialog ──
const editDialogVisible = ref(false)
const editingUser = ref<UserOut | null>(null)
const editForm = reactive({
  username: '',
  display_name: '',
  role_id: undefined as number | undefined,
})

function openEdit(user: UserOut): void {
  editingUser.value = user
  editForm.username = user.username
  editForm.display_name = user.display_name
  editForm.role_id = user.role_id
  editDialogVisible.value = true
}

async function handleEditSave(): Promise<void> {
  if (!editingUser.value || !editForm.role_id) return

  // Check role change boundary
  const selectedRole = roles.value.find((r) => r.id === editForm.role_id)
  const newRoleIsSuperadmin = selectedRole?.is_superadmin ?? false
  if (!canChangeRole(editingUser.value, newRoleIsSuperadmin)) {
    ElMessage.error('至少需要保留一个超管用户，不能将该用户角色改为非超管')
    return
  }

  saving.value = true
  try {
    await updateUser(editingUser.value.id, {
      display_name: editForm.display_name,
      role_id: editForm.role_id,
    })
    ElMessage.success('用户更新成功')
    editDialogVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '更新用户失败'))
  } finally {
    saving.value = false
  }
}

// ── Reset Password Dialog ──
const resetPwdDialogVisible = ref(false)
const resetPwdTarget = ref<UserOut | null>(null)
const resetPwdForm = reactive({
  password: '',
  confirmPassword: '',
})

function openResetPassword(user: UserOut): void {
  resetPwdTarget.value = user
  resetPwdForm.password = ''
  resetPwdForm.confirmPassword = ''
  resetPwdDialogVisible.value = true
}

async function handleResetPassword(): Promise<void> {
  if (!resetPwdTarget.value) return
  if (!resetPwdForm.password || resetPwdForm.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (resetPwdForm.password !== resetPwdForm.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  saving.value = true
  try {
    await resetPassword(resetPwdTarget.value.id, resetPwdForm.password)
    ElMessage.success('密码已重置')
    resetPwdDialogVisible.value = false
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '重置密码失败'))
  } finally {
    saving.value = false
  }
}

// ── Toggle status ──
async function handleToggleStatus(user: UserOut): Promise<void> {
  const action = user.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确定要${action}用户「${user.username}」吗？`,
      `${action}确认`,
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  try {
    await toggleUserStatus(user.id, !user.is_active)
    ElMessage.success(`用户已${action}`)
    await loadData()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, `${action}失败`))
  }
}

// ── Dropdown command handler ──
function handleDropdownCommand(command: string, user: UserOut): void {
  if (command === 'resetPassword') {
    openResetPassword(user)
  } else if (command === 'delete') {
    handleDelete(user)
  }
}

// ── Delete ──
async function handleDelete(user: UserOut): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户「${user.username}」吗？此操作不可撤销。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  try {
    await deleteUser(user.id)
    ElMessage.success('用户已删除')
    await loadData()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '删除失败'))
  }
}
</script>

<style lang="scss" scoped>
.dropdown-danger-text {
  color: $color-destructive;
}
</style>
