/**
 * 菜单图标注册表
 *
 * 后端菜单 v2 下发的 `icon` 是 Element Plus 图标组件名（如 "Location"、"Money"）。
 * 这里把侧栏/移动端/搜索弹窗可能用到的图标显式登记为组件，避免 `import * as`
 * 把整套图标库打进主包；未知/缺失图标回退到通用「菜单」图标，保证不白屏。
 */
import type { Component } from 'vue'
import {
  Box,
  Briefcase,
  Calendar,
  ChatDotRound,
  ChatLineSquare,
  Checked,
  Clock,
  Collection,
  Connection,
  Cpu,
  DataAnalysis,
  DataBoard,
  Document,
  DocumentCopy,
  Download,
  Files,
  FirstAidKit,
  Folder,
  FolderOpened,
  Grid,
  Histogram,
  HomeFilled,
  InfoFilled,
  Key,
  List,
  Location,
  Lock,
  MapLocation,
  Menu,
  Message,
  Money,
  Monitor,
  Notebook,
  Notification,
  Odometer,
  OfficeBuilding,
  Operation,
  PieChart,
  Postcard,
  QuestionFilled,
  Reading,
  Refresh,
  Search,
  Select,
  Setting,
  Share,
  School,
  Stamp,
  Star,
  StarFilled,
  Sunny,
  Switch,
  Ticket,
  Tools,
  TrendCharts,
  Upload,
  UploadFilled,
  User,
  Warning,
} from '@element-plus/icons-vue'

/** 后端菜单 icon 名 → 组件（key 必须与后端下发字符串完全一致） */
const MENU_ICON_MAP: Readonly<Record<string, Component>> = {
  Box,
  Briefcase,
  Calendar,
  ChatDotRound,
  ChatLineSquare,
  Checked,
  Clock,
  Collection,
  Connection,
  Cpu,
  DataAnalysis,
  DataBoard,
  Document,
  DocumentCopy,
  Download,
  Files,
  FirstAidKit,
  Folder,
  FolderOpened,
  Grid,
  Histogram,
  HomeFilled,
  InfoFilled,
  Key,
  List,
  Location,
  Lock,
  MapLocation,
  Menu,
  Message,
  Money,
  Monitor,
  Notebook,
  Notification,
  Odometer,
  OfficeBuilding,
  Operation,
  PieChart,
  Postcard,
  QuestionFilled,
  Reading,
  Refresh,
  Search,
  Select,
  Setting,
  Share,
  School,
  Stamp,
  Star,
  StarFilled,
  Sunny,
  Switch,
  Ticket,
  Tools,
  TrendCharts,
  Upload,
  UploadFilled,
  User,
  Warning,
}

/** 未知图标回退组件 */
const FALLBACK_MENU_ICON = Menu

/**
 * 把后端下发的图标名解析为可渲染组件。
 * @param name 后端菜单 icon 字段（可能缺失/未知）
 * @returns Element Plus 图标组件；未知/缺失时回退通用菜单图标
 */
export function resolveMenuIcon(name?: string): Component {
  if (name && Object.prototype.hasOwnProperty.call(MENU_ICON_MAP, name)) {
    return MENU_ICON_MAP[name]
  }
  return FALLBACK_MENU_ICON
}
