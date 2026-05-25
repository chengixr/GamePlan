/**
 * 10 种预设头像 SVG（Neon Arcade 风格几何图形）
 * 每个头像 64x64，不同配色和形状组合
 */

const COLORS = [
  { bg: '#e94560', fg: '#0f3460' },  // 霓虹红
  { bg: '#00e5ff', fg: '#0a0a1a' },  // 霓虹青
  { bg: '#ffb800', fg: '#1a1a2e' },  // 琥珀
  { bg: '#ff2d78', fg: '#0d0d1a' },  // 品红
  { bg: '#7c3aed', fg: '#e8e8ef' },  // 紫
  { bg: '#10b981', fg: '#06060b' },  // 翠绿
  { bg: '#f97316', fg: '#151528' },  // 橙
  { bg: '#3b82f6', fg: '#e8e8ef' },  // 蓝
  { bg: '#ec4899', fg: '#0d0d1a' },  // 粉
  { bg: '#06b6d4', fg: '#0a0a1a' },  // 青
]

const SHAPES = [
  // 三角形
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><polygon points="32,14 56,50 8,50" fill="${c.fg}" opacity="0.8"/></svg>`,
  // 菱形
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><polygon points="32,8 56,32 32,56 8,32" fill="${c.fg}" opacity="0.8"/></svg>`,
  // 十字
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><rect x="22" y="10" width="20" height="44" rx="3" fill="${c.fg}" opacity="0.8"/><rect x="10" y="22" width="44" height="20" rx="3" fill="${c.fg}" opacity="0.8"/></svg>`,
  // 圆形靶
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><circle cx="32" cy="32" r="22" fill="${c.fg}" opacity="0.3"/><circle cx="32" cy="32" r="14" fill="${c.fg}" opacity="0.6"/><circle cx="32" cy="32" r="7" fill="${c.fg}" opacity="0.9"/></svg>`,
  // 条纹
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><rect x="0" y="8" width="64" height="12" fill="${c.fg}" opacity="0.5"/><rect x="0" y="26" width="64" height="12" fill="${c.fg}" opacity="0.7"/><rect x="0" y="44" width="64" height="12" fill="${c.fg}" opacity="0.5"/></svg>`,
  // 六边形
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><polygon points="32,10 52,22 52,42 32,54 12,42 12,22" fill="${c.fg}" opacity="0.8"/></svg>`,
  // 箭头
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><polygon points="18,16 46,32 18,48" fill="${c.fg}" opacity="0.8"/></svg>`,
  // 方块堆叠
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><rect x="10" y="10" width="20" height="20" rx="2" fill="${c.fg}" opacity="0.5"/><rect x="34" y="34" width="20" height="20" rx="2" fill="${c.fg}" opacity="0.9"/><rect x="22" y="22" width="20" height="20" rx="2" fill="${c.fg}" opacity="0.7"/></svg>`,
  // 月牙
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><circle cx="36" cy="32" r="20" fill="${c.fg}" opacity="0.8"/><circle cx="44" cy="24" r="16" fill="${c.bg}"/></svg>`,
  // 闪电
  (c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="${c.bg}"/><polygon points="34,8 20,36 30,36 24,56 44,26 34,26 40,8" fill="${c.fg}" opacity="0.85"/></svg>`,
]

export const PRESET_AVATARS = COLORS.map((color, i) => ({
  id: `${i + 1}`,
  svg: SHAPES[i](color),
  color: color.bg,
}))

export function getAvatarSVG(avatarId) {
  const av = PRESET_AVATARS.find(a => a.id === String(avatarId))
  return av ? av.svg : PRESET_AVATARS[0].svg
}
