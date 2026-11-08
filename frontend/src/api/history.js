/**
 * 云开发数据库 parse_history 集合读写服务
 * AC-009, AC-010: 按 openid 天然隔离，端侧直写直查
 */

const COLLECTION_NAME = 'parse_history'
const LOCAL_STORAGE_KEY = 'renlink_parse_history'

/**
 * 记录解析历史
 * @param {object} record 
 * @returns {Promise<void>}
 */
export async function addHistoryRecord(record) {
  const item = {
    original_url: record.original_url || '',
    resolved_url: record.resolved_url || '',
    platform: record.platform || 'douyin',
    content_type: record.content_type || 'video',
    title: record.title || '无标题',
    cover: record.cover || '',
    item_count: record.item_count || 1,
    create_time: record.create_time || Date.now()
  }

  // #ifdef MP-WEIXIN
  try {
    if (typeof wx !== 'undefined' && wx.cloud) {
      const db = wx.cloud.database()
      await db.collection(COLLECTION_NAME).add({
        data: item
      })
      return
    }
  } catch (err) {
    console.warn('parse_history db add fail, fallback local:', err)
  }
  // #endif

  // 本地存储兜底
  try {
    const list = uni.getStorageSync(LOCAL_STORAGE_KEY) || []
    list.unshift({ ...item, _id: 'local_' + Date.now() })
    uni.setStorageSync(LOCAL_STORAGE_KEY, list.slice(0, 50))
  } catch (e) {
    console.error('save history to storage failed:', e)
  }
}

/**
 * 查询历史记录列表（分页，按 create_time 倒序）
 * @param {{ page: number, pageSize: number }} param0 
 * @returns {Promise<Array<object>>}
 */
export async function getHistoryRecords({ page = 1, pageSize = 10 } = {}) {
  // #ifdef MP-WEIXIN
  try {
    if (typeof wx !== 'undefined' && wx.cloud) {
      const db = wx.cloud.database()
      const skip = (page - 1) * pageSize
      const res = await db.collection(COLLECTION_NAME)
        .where({})
        .orderBy('create_time', 'desc')
        .skip(skip)
        .limit(pageSize)
        .get()
      return res.data || []
    }
  } catch (err) {
    console.warn('parse_history db get fail, fallback local:', err)
  }
  // #endif

  // 本地存储兜底
  try {
    const list = uni.getStorageSync(LOCAL_STORAGE_KEY) || []
    const start = (page - 1) * pageSize
    return list.slice(start, start + pageSize)
  } catch (e) {
    return []
  }
}
