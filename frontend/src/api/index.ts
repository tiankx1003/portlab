import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

export async function getHealth(): Promise<ApiResponse<{ status: string }>> {
  const res = await http.get<ApiResponse<{ status: string }>>('/health')
  return res.data
}

export default http
