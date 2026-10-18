/**
 * 影像库 API（W22 契约 §2 /media/photos）
 *
 * - 列表/CRUD：走 `get/post/put/del`（自动解包 envelope）；
 * - 拍摄点多期：`getPhotoCompare(spot_key)` 返回同拍摄点的多期照片；
 * - 对比图：`generateCompareImage(ids)` 返回 PNG Blob（弹窗预览用），
 *   `downloadCompareImage(ids)` 走 GET 版本并解析 Content-Disposition 触发下载。
 */
import request, { get, post, put, del, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

/** 影像归档记录（photo_archives） */
export interface PhotoArchive {
  id: number
  file_url: string
  file_name?: string | null
  file_size?: number | null
  mime_type?: string | null
  village_id?: number | null
  school_id?: number | null
  project_id?: number | null
  tag?: string | null
  spot_key?: string | null
  taken_at?: string | null
  gps_lat?: number | null
  gps_lng?: number | null
  uploader_id?: number | null
  shot_source?: string | null
  created_at?: string | null
  updated_at?: string | null
}

/** 列表筛选参数（契约 §2） */
export interface PhotoArchiveQuery {
  page?: number
  page_size?: number
  village_id?: number | null
  school_id?: number | null
  project_id?: number | null
  tag?: string
  date_from?: string
  date_to?: string
}

/** 新建归档入参：file_url 必填，其余由后端 EXIF/GPS 补全 */
export interface PhotoArchiveCreate {
  file_url: string
  file_name?: string
  file_size?: number
  mime_type?: string
  village_id?: number | null
  school_id?: number | null
  project_id?: number | null
  tag?: string | null
  spot_key?: string | null
  taken_at?: string | null
}

/** 同拍摄点多期照片 */
export interface PhotoCompareItem {
  id: number
  file_url: string
  taken_at?: string | null
}

/** 列表（后端 ok_list envelope，调用方用 unwrapList 解包） */
export const getPhotos = (params?: PhotoArchiveQuery) => get('/media/photos', params)

/** 注册归档记录（上传成功后调用） */
export const createPhoto = (data: PhotoArchiveCreate) => post('/media/photos', data)

/** 更新归档信息（标签/拍摄点/关联对象/拍摄时间） */
export const updatePhoto = (id: number, data: Partial<PhotoArchiveCreate>) =>
  put(`/media/photos/${id}`, data)

/** 删除归档（软删） */
export const deletePhoto = (id: number) => del(`/media/photos/${id}`)

/** 同拍摄点多期照片（按拍摄时间升序） */
export const getPhotoCompare = (spotKey: string) =>
  get('/media/photos/compare', { spot_key: spotKey })

/**
 * 生成合成对比 PNG（POST body ids[]）。
 * 返回 Blob 供弹窗内 `URL.createObjectURL` 预览。
 */
export const generateCompareImage = (ids: number[]): Promise<Blob> =>
  apiRequest<Blob>({
    method: 'POST',
    url: '/media/photos/compare-image',
    data: { ids },
    responseType: 'blob',
  })

/**
 * 下载合成对比 PNG（GET 版本，便于浏览器按 Content-Disposition 命名）。
 * GET 参数使用逗号分隔的 ids（后端两种形态均支持）。
 */
export const downloadCompareImage = (ids: number[]) =>
  downloadBlobAsFile(
    () =>
      request.get('/media/photos/compare-image', {
        params: { ids: ids.join(',') },
        responseType: 'blob',
      }),
    { fallbackFileName: '影像对比图.png' }
  )
