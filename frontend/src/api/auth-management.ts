// 用户/角色管理 API 客户端
import client from './client'

// ── Users ──

export interface UserOut {
  id: number
  username: string
  display_name: string
  role_id: number
  role_name: string
  is_active: boolean
  is_superadmin: boolean
  last_login_at: string | null
}

export async function getUsers(): Promise<UserOut[]> {
  const { data } = await client.get<UserOut[]>('/api/auth/users')
  return data
}

export async function createUser(payload: {
  username: string
  display_name: string
  password: string
  role_id: number
}): Promise<UserOut> {
  const { data } = await client.post<UserOut>('/api/auth/users', payload)
  return data
}

export async function updateUser(
  userId: number,
  payload: { display_name?: string; role_id?: number },
): Promise<UserOut> {
  const { data } = await client.put<UserOut>(`/api/auth/users/${userId}`, payload)
  return data
}

export async function deleteUser(userId: number): Promise<void> {
  await client.delete(`/api/auth/users/${userId}`)
}

export async function toggleUserStatus(
  userId: number,
  isActive: boolean,
): Promise<UserOut> {
  const { data } = await client.patch<UserOut>(`/api/auth/users/${userId}/status`, {
    is_active: isActive,
  })
  return data
}

export async function resetPassword(
  userId: number,
  newPassword: string,
): Promise<void> {
  await client.put(`/api/auth/users/${userId}/password`, {
    new_password: newPassword,
  })
}

// ── Roles ──

export interface RoleOut {
  id: number
  name: string
  description: string
  is_superadmin: boolean
  user_count: number
}

export async function getRoles(): Promise<RoleOut[]> {
  const { data } = await client.get<RoleOut[]>('/api/auth/roles')
  return data
}

export async function createRole(payload: {
  name: string
  description: string
}): Promise<RoleOut> {
  const { data } = await client.post<RoleOut>('/api/auth/roles', payload)
  return data
}

export async function updateRole(
  roleId: number,
  payload: { name?: string; description?: string },
): Promise<RoleOut> {
  const { data } = await client.put<RoleOut>(`/api/auth/roles/${roleId}`, payload)
  return data
}

export async function deleteRole(roleId: number): Promise<void> {
  await client.delete(`/api/auth/roles/${roleId}`)
}

// ── Permissions ──

export interface PermissionOut {
  code: string
  name: string
  group_name: string
}

export async function getPermissions(): Promise<PermissionOut[]> {
  const { data } = await client.get<PermissionOut[]>('/api/auth/permissions')
  return data
}

export async function getRolePermissions(roleId: number): Promise<string[]> {
  const { data } = await client.get<string[]>(`/api/auth/roles/${roleId}/permissions`)
  return data
}

export async function updateRolePermissions(
  roleId: number,
  permissionCodes: string[],
): Promise<void> {
  await client.put(`/api/auth/roles/${roleId}/permissions`, {
    permission_codes: permissionCodes,
  })
}
