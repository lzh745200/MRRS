/**
 * 组织树节点规范化工具
 *
 * 解决 Element Plus el-tree / el-tree-select 无法处理数值型 id 的问题：
 * el-tree 内部通过 setAttribute('id', ...) 设置 DOM id 属性，
 * 当 id 为 0 或纯数字时触发 DOMException: "'0' is not a valid attribute name"
 *
 * 根因修复建议：后端 API 返回 id 为字符串（在路由/服务层统一转换）
 * 当前前端侧统一用此工具兜底。
 */

/**
 * 规范化前的宽松节点形态。
 *
 * 后端各树形接口（如 `/organizations/tree`）字段命名与类型不统一：
 * id 可能是数值型，label/name 可能互相缺失，children 可能不是数组。
 * 因此所有字段均为可选，并允许 null（JSON 反序列化会产出 null）。
 */
export interface RawTreeNode {
  id?: string | number | null
  key?: string | number | null
  name?: string | null
  label?: string | null
  leaf?: boolean | null
  children?: RawTreeNode[] | null
}

/**
 * 规范化后的节点形态。
 *
 * `id` 保证为非纯数字开头的字符串（可直接用于 DOM id 属性）；
 * `label` 沿用原实现的 `label ?? name` 回退，两者都缺失时为 undefined，
 * 故此处如实声明为可选而不谎报为 string。
 */
export interface NormalizedTreeNode {
  id: string
  name?: string | null
  label?: string | null
  children?: NormalizedTreeNode[]
  leaf: boolean
}

/** 生成稳定的、基于内容的回退键 */
function makeStableId(node: RawTreeNode): string {
  const raw = String(
    node.id ?? node.key ?? `_node_${(node.name || node.label || '').substring(0, 20)}`
  )
  // 确保以字母开头 — 纯数字 id（如 0）会导致 DOM setAttribute('0', …) 异常
  return /^[0-9]/.test(raw) ? `_${raw}` : raw
}

/** 将单节点 id 转为字符串，白名单属性，递归标准化子节点 */
export function normalizeTreeNode(node: RawTreeNode): NormalizedTreeNode {
  // 把“children 是数组”的判定结果固化到 childrenArray，使 TS 的类型守卫
  // 稳定收窄（对属性访问 node.children 直接守卫不可靠）。
  //
  // children 在类型上只可能是 RawTreeNode[] | null，但运行时后端 JSON
  // 可能给出字符串/类数组等非数组值。因此 else 分支仍读原始的
  // rawChildren，保留 !rawChildren?.length 的原表达式——若改成
  // !childrenArray?.length 则非数组但带 length 的值（如 'abc'）会得到
  // 不同的 leaf 结果。Array.isArray 无副作用，上述改写与原实现逐值等价。
  const rawChildren = node.children
  const childrenArray = Array.isArray(rawChildren) ? rawChildren : null

  const children = childrenArray
    ? childrenArray.length
      ? normalizeTreeNodes(childrenArray)
      : []
    : undefined

  return {
    id: makeStableId(node),
    name: node.name,
    label: node.label ?? node.name,
    children,
    leaf: childrenArray ? childrenArray.length === 0 : (node.leaf ?? !rawChildren?.length),
  }
}

/** 递归规范化整棵树 */
export function normalizeTreeNodes(nodes: RawTreeNode[]): NormalizedTreeNode[] {
  return nodes.map((node) => normalizeTreeNode(node))
}
