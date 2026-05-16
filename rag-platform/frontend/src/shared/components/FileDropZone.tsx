/**
 * 可复用的拖拽上传区域组件
 *
 * 支持拖拽和点击选择文件，限制文件类型和数量
 */
import { useCallback } from 'react'
import { Upload, message } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadRequestOption } from '@rc-component/upload/lib/interface'

/** 支持的文件扩展名 */
const ACCEPTED_EXTENSIONS = ['.pdf', '.txt', '.md', '.html', '.htm', '.epub']

/** 单次最大文件数 */
const MAX_FILES = 50

export interface FileDropZoneProps {
  /** 上传回调 */
  onFiles: (files: File[]) => void
  /** 是否禁用 */
  disabled?: boolean
}

export default function FileDropZone({ onFiles, disabled }: FileDropZoneProps) {
  /** 校验文件列表 */
  const validateFiles = useCallback((fileList: File[]): File[] => {
    // 数量校验
    if (fileList.length > MAX_FILES) {
      message.warning(`单次最多上传 ${MAX_FILES} 个文件`)
      fileList = fileList.slice(0, MAX_FILES)
    }

    // 类型校验
    const validFiles: File[] = []
    const rejected: string[] = []

    fileList.forEach((file) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase()
      if (ACCEPTED_EXTENSIONS.includes(ext)) {
        validFiles.push(file)
      } else {
        rejected.push(file.name)
      }
    })

    if (rejected.length > 0) {
      message.error(`不支持的文件格式：${rejected.join('、')}`)
    }

    return validFiles
  }, [])

  /** 处理文件选择 */
  const handleFiles = useCallback(
    (files: File[]) => {
      const valid = validateFiles(files)
      if (valid.length > 0) {
        onFiles(valid)
      }
    },
    [validateFiles, onFiles]
  )

  // antd Upload 的 customRequest，阻止自动上传
  const customUpload = useCallback(
    (options: UploadRequestOption) => {
      handleFiles([options.file as unknown as File])
      options.onSuccess?.(null)
    },
    [handleFiles]
  )

  return (
    <Upload.Dragger
      multiple
      accept={ACCEPTED_EXTENSIONS.join(',')}
      customRequest={customUpload}
      showUploadList={false}
      disabled={disabled}
    >
      <p className="ant-upload-drag-icon">
        <InboxOutlined />
      </p>
      <p className="ant-upload-text">
        拖拽 PDF / TXT / Markdown / HTML / EPUB 到此处上传，或点击选择文件
      </p>
      <p className="ant-upload-hint">单次最多 {MAX_FILES} 个文件</p>
    </Upload.Dragger>
  )
}
