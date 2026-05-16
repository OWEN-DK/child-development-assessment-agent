/**
 * 管道列表状态管理
 *
 * 管理管道列表的加载、搜索、筛选、分页等状态
 */
import { create } from 'zustand'
import type { PipelineListItem } from '@/entities/pipeline/types'
import * as pipelineApi from '@/api/pipeline/pipeline'

/** 管道列表状态 */
interface PipelineListState {
  // 列表数据
  pipelines: PipelineListItem[]
  total: number
  isLoading: boolean
  error: string | null

  // 筛选与分页
  searchQuery: string
  statusFilter: string | null
  page: number
  pageSize: number

  // 操作方法
  loadPipelines: () => Promise<void>
  deletePipeline: (id: string) => Promise<void>
  setSearchQuery: (query: string) => void
  setStatusFilter: (status: string | null) => void
  setPage: (page: number) => void
  setPageSize: (pageSize: number) => void
  resetFilters: () => void
}

export const usePipelineListStore = create<PipelineListState>((set, get) => ({
  // 初始状态
  pipelines: [],
  total: 0,
  isLoading: false,
  error: null,

  searchQuery: '',
  statusFilter: null,
  page: 1,
  pageSize: 20,

  // 加载管道列表
  loadPipelines: async () => {
    const state = get()
    set({ isLoading: true, error: null })

    try {
      const result = await pipelineApi.getPipelines({
        page: state.page,
        pageSize: state.pageSize,
        status: state.statusFilter || undefined,
        keyword: state.searchQuery || undefined,
      })

      set({
        pipelines: result.items,
        total: result.total,
        isLoading: false,
      })
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : '加载失败',
      })
    }
  },

  // 删除管道
  deletePipeline: async (id) => {
    set({ isLoading: true, error: null })

    try {
      await pipelineApi.deletePipeline(id)

      // 重新加载列表
      const state = get()
      await state.loadPipelines()
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : '删除失败',
      })
    }
  },

  // 设置搜索关键词
  setSearchQuery: (query) => {
    set({ searchQuery: query, page: 1 })
    // 自动重新加载
    get().loadPipelines()
  },

  // 设置状态筛选
  setStatusFilter: (status) => {
    set({ statusFilter: status, page: 1 })
    // 自动重新加载
    get().loadPipelines()
  },

  // 设置页码
  setPage: (page) => {
    set({ page })
    get().loadPipelines()
  },

  // 设置每页数量
  setPageSize: (pageSize) => {
    set({ pageSize, page: 1 })
    get().loadPipelines()
  },

  // 重置筛选
  resetFilters: () => {
    set({
      searchQuery: '',
      statusFilter: null,
      page: 1,
    })
    get().loadPipelines()
  },
}))
