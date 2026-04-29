export interface CountryOption {
  code: string
  label: string
}

export const COUNTRY_OPTIONS: CountryOption[] = [
  { code: 'EU', label: 'EU - 欧盟' },
  { code: 'ZZ', label: 'ZZ - 无法识别国家' },
  { code: 'CN', label: 'CN - 中国' },
  { code: 'US', label: 'US - 美国' },
  { code: 'CA', label: 'CA - 加拿大' },
  { code: 'MX', label: 'MX - 墨西哥' },
  { code: 'GB', label: 'GB - 英国' },
  { code: 'CZ', label: 'CZ - 捷克' },
  { code: 'DE', label: 'DE - 德国' },
  { code: 'FR', label: 'FR - 法国' },
  { code: 'IT', label: 'IT - 意大利' },
  { code: 'ES', label: 'ES - 西班牙' },
  { code: 'IN', label: 'IN - 印度' },
  { code: 'JP', label: 'JP - 日本' },
  { code: 'AU', label: 'AU - 澳大利亚' },
  { code: 'AE', label: 'AE - 阿联酋' },
  { code: 'TR', label: 'TR - 土耳其' },
  { code: 'SG', label: 'SG - 新加坡' },
  { code: 'BR', label: 'BR - 巴西' },
  { code: 'NL', label: 'NL - 荷兰' },
  { code: 'RO', label: 'RO - 罗马尼亚' },
  { code: 'SA', label: 'SA - 沙特阿拉伯' },
  { code: 'SE', label: 'SE - 瑞典' },
  { code: 'PL', label: 'PL - 波兰' },
  { code: 'BE', label: 'BE - 比利时' },
  { code: 'IE', label: 'IE - 爱尔兰' },
]

export function getCountryLabel(code: string | null | undefined): string {
  if (!code) return '-'
  const normalized = code.toUpperCase()
  return COUNTRY_OPTIONS.find((item) => item.code === normalized)?.label || normalized
}
