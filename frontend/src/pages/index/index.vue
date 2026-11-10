<template>
  <view class="container">
    <!-- 剪贴板检测浮动提示条 (AC-001) -->
    <view v-if="clipboardPromptVisible" class="clipboard-bar">
      <view class="clipboard-text">检测到社媒分享链接，是否填入？</view>
      <view class="clipboard-actions">
        <button class="btn-fill" size="mini" @tap="applyClipboardUrl">立即填入</button>
        <text class="btn-dismiss" @tap="dismissClipboardPrompt">忽略</text>
      </view>
    </view>

    <!-- 顶部卡片：输入区 (AC-002) -->
    <view class="card input-card">
      <textarea
        v-model="inputUrl"
        class="url-textarea"
        placeholder="请粘贴抖音或小红书的分享链接..."
        placeholder-class="placeholder-style"
        :maxlength="1000"
        @input="onInputChange"
      />
      <view class="input-tools">
        <text v-if="inputUrl" class="tool-btn" @tap="clearInput">清空</text>
        <button class="tool-btn-paste" size="mini" @tap="pasteFromClipboard">粘贴剪贴板</button>
      </view>
    </view>

    <!-- 主解析按钮 -->
    <view class="action-section">
      <button
        class="parse-btn"
        :class="{ loading: isParsing, disabled: !isUrlReady }"
        :disabled="isParsing || !isUrlReady"
        @tap="handleParse"
      >
        <text v-if="isParsing">正在高速解析中...</text>
        <text v-else>一键解析提取</text>
      </button>
    </view>

    <!-- 解析错误提示 (AC-007) -->
    <view v-if="errorMessage" class="error-banner">
      <text class="error-text">{{ errorMessage }}</text>
      <text class="error-retry-btn" @tap="handleParse">重试</text>
    </view>

    <!-- 解析中骨架屏 -->
    <view v-if="isParsing" class="card skeleton-card">
      <view class="skeleton-shimmer"></view>
      <view class="skeleton-text">正在高速解析中，请稍候...</view>
    </view>

    <!-- 解析结果展示卡片 (AC-003, AC-004) -->
    <view v-if="parseResult && !isParsing" class="card result-card">
      <view class="result-header">
        <view class="tags-row">
          <text class="tag tag-platform" :class="parseResult.platform">
            {{ parseResult.platform === 'douyin' ? '抖音' : '小红书' }}
          </text>
          <text class="tag tag-type">
            {{ parseResult.content_type === 'video' ? '无水印视频' : '图文集合' }}
          </text>
        </view>
        <text class="result-title">{{ parseResult.title || '无标题内容' }}</text>
      </view>

      <!-- 视频模式 (AC-003) -->
      <view v-if="parseResult.content_type === 'video'" class="video-preview-box">
        <image class="video-cover" :src="videoCoverUrl" mode="aspectFill" />
        <view class="play-icon-overlay">
          <view class="play-triangle"></view>
        </view>
        <view class="save-actions">
          <button
            class="save-btn"
            :disabled="isSaving"
            @tap="saveSingleVideo"
          >
            {{ isSaving ? saveProgressText : '保存视频到相册' }}
          </button>
        </view>
      </view>

      <!-- 图文模式 (AC-004) -->
      <view v-if="parseResult.content_type === 'note'" class="note-preview-box">
        <view class="note-header-info">
          <text class="note-count">共 {{ parseResult.items.length }} 张高清无水印图片</text>
        </view>
        <view class="image-grid">
          <view
            v-for="(item, idx) in parseResult.items"
            :key="idx"
            class="grid-item"
            @tap="previewImageItem(idx)"
          >
            <image class="thumb-img" :src="item.cover || item.remoteUrl" mode="aspectFill" />
            <view class="item-badge">{{ idx + 1 }}</view>
            <!-- 单项失败提示与独立重试 (AC-005) -->
            <view v-if="failedItems[idx]" class="item-fail-mask" @tap.stop="retrySingleItem(idx)">
              <text class="fail-icon">✕</text>
              <text class="fail-retry-text">重试</text>
            </view>
          </view>
        </view>

        <!-- 步进进度条 -->
        <view v-if="isSaving" class="progress-box">
          <text class="progress-text">{{ saveProgressText }}</text>
          <progress :percent="savePercent" stroke-width="4" activeColor="#07C160" />
        </view>

        <!-- 保存全部与 ZIP 导出操作区 (AC-004, AC-006) -->
        <view class="note-actions">
          <button
            class="save-btn"
            :disabled="isSaving"
            @tap="saveAllImages"
          >
            一键保存全部图片 (共 {{ parseResult.items.length }} 张)
          </button>
          <button
            class="zip-btn"
            :disabled="isZipping || isSaving"
            @tap="handleExportZip"
          >
            {{ isZipping ? '正在打包 ZIP...' : '打包导出 ZIP 并转发' }}
          </button>
        </view>
      </view>
    </view>
    <!-- 底部版权声明与投诉入口 (TASK-008 / AC-008) -->
    <view class="footer-copyright">
      <text class="copyright-text">仅供个人备份，版权归原作者所有</text>
      <text class="complaint-link" @tap="goToComplaint">侵权投诉</text>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onShow, onLoad } from '@dcloudio/uni-app'
import { extractValidUrl, parseUrl, stageMedia, createZip, stageFileUrl } from '../../api/parse'
import { addHistoryRecord } from '../../api/history'
import { ensureAlbumPermission, saveVideoToAlbum, saveImageToAlbum } from '../../utils/album'
import { getErrorMessage } from '../../utils/errors'

const inputUrl = ref('')
const clipboardUrl = ref('')
const clipboardPromptVisible = ref(false)
const isParsing = ref(false)
const errorMessage = ref('')
const parseResult = ref(null)

const isSaving = ref(false)
const saveProgressText = ref('')
const savePercent = ref(0)
const isZipping = ref(false)
const failedItems = ref({})

const isUrlReady = computed(() => {
  const { valid } = extractValidUrl(inputUrl.value)
  return valid
})

const videoCoverUrl = computed(() => {
  if (!parseResult.value) return ''
  return parseResult.value.items?.[0]?.cover || parseResult.value.items?.[0]?.remoteUrl || ''
})

onLoad((query) => {
  if (query && query.url) {
    const decoded = decodeURIComponent(query.url)
    inputUrl.value = decoded
    handleParse()
  }
})

onShow(() => {
  const autoUrl = uni.getStorageSync('renlink_auto_parse_url')
  if (autoUrl) {
    uni.removeStorageSync('renlink_auto_parse_url')
    inputUrl.value = autoUrl
    handleParse()
  } else {
    checkClipboard()
  }
})

function checkClipboard() {
  uni.getClipboardData({
    success(res) {
      const data = res.data
      if (data && data !== clipboardUrl.value && data !== inputUrl.value) {
        const { valid, url } = extractValidUrl(data)
        if (valid) {
          clipboardUrl.value = url
          clipboardPromptVisible.value = true
        }
      }
    },
    fail() {
      // 静默降级
    }
  })
}

function applyClipboardUrl() {
  inputUrl.value = clipboardUrl.value
  clipboardPromptVisible.value = false
  // 清空剪贴板防重复
  uni.setClipboardData({
    data: '',
    success() {
      uni.hideToast()
    }
  })
}

function dismissClipboardPrompt() {
  clipboardPromptVisible.value = false
}

function clearInput() {
  inputUrl.value = ''
  errorMessage.value = ''
  parseResult.value = null
}

function pasteFromClipboard() {
  uni.getClipboardData({
    success(res) {
      if (res.data) {
        inputUrl.value = res.data
        onInputChange()
      }
    }
  })
}

function onInputChange() {
  errorMessage.value = ''
}

async function handleParse() {
  if (!isUrlReady.value || isParsing.value) return
  isParsing.value = true
  errorMessage.value = ''
  failedItems.value = {}

  try {
    const res = await parseUrl(inputUrl.value)
    parseResult.value = res

    // 自动落库 parse_history (AC-010)
    const cover = res.items?.[0]?.cover || res.items?.[0]?.remoteUrl || ''
    addHistoryRecord({
      original_url: res.source_url || inputUrl.value,
      resolved_url: res.resolved_url || '',
      platform: res.platform,
      content_type: res.content_type,
      title: res.title,
      cover,
      item_count: res.item_count || res.items?.length || 1,
      create_time: Date.now()
    }).catch(e => console.warn('History auto-add error:', e))
  } catch (err) {
    parseResult.value = null
    errorMessage.value = err.message || getErrorMessage('PARSE_FAILED')
  } finally {
    isParsing.value = false
  }
}

async function saveSingleVideo() {
  const hasAuth = await ensureAlbumPermission()
  if (!hasAuth) {
    uni.showToast({ title: '需要相册权限', icon: 'none' })
    return
  }

  isSaving.value = true
  saveProgressText.value = '正在转存视频...'
  try {
    const videoItem = parseResult.value.items[0]
    const staged = await stageMedia(videoItem, parseResult.value.task_id)

    // #ifdef MP-WEIXIN
    if (staged.fileID && staged.fileID.startsWith('cloud://')) {
      const downloadRes = await new Promise((resolve, reject) => {
        wx.cloud.downloadFile({
          fileID: staged.fileID,
          success: resolve,
          fail: reject
        })
      })
      await saveVideoToAlbum(downloadRes.tempFilePath)
      uni.showToast({ title: '视频已保存到相册', icon: 'success' })
      return
    }
    // #endif

    // #ifndef MP-WEIXIN
    downloadToDisk(staged.fileID)
    uni.showToast({ title: '已开始下载视频', icon: 'success' })
    return
    // #endif

    await saveVideoToAlbum(staged.fileID)
    uni.showToast({ title: '视频已保存到相册', icon: 'success' })
  } catch (err) {
    const msg = err?.message || '保存视频失败，请重试'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    isSaving.value = false
  }
}

function previewImageItem(index) {
  if (!parseResult.value || !parseResult.value.items) return
  const urls = parseResult.value.items.map(it => it.remoteUrl || it.cover)
  uni.previewImage({
    current: urls[index],
    urls
  })
}

function downloadToDisk(fileID) {
  // #ifndef MP-WEIXIN
  const link = document.createElement('a')
  link.href = stageFileUrl(fileID)
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  // #endif
}

async function saveAllImages() {
  const hasAuth = await ensureAlbumPermission()
  if (!hasAuth) {
    uni.showToast({ title: '需要相册权限', icon: 'none' })
    return
  }

  const items = parseResult.value.items
  isSaving.value = true
  failedItems.value = {}
  let successCount = 0

  for (let i = 0; i < items.length; i++) {
    saveProgressText.value = `正在转存并保存第 (${i + 1}/${items.length}) 张图片...`
    savePercent.value = Math.floor(((i + 1) / items.length) * 100)

    try {
      await saveSingleImageItem(items[i])
      successCount++
    } catch (err) {
      console.error(`Item ${i} save error:`, err)
      failedItems.value = { ...failedItems.value, [i]: true }
    }
  }

  isSaving.value = false
  if (successCount === items.length) {
    uni.showToast({ title: '全部图片已保存到相册', icon: 'success' })
  } else if (successCount === 0) {
    uni.showToast({ title: '本次未能保存任何图片，请检查网络或相册权限', icon: 'none', duration: 3500 })
  } else {
    uni.showToast({ title: `保存完成，有 ${items.length - successCount} 项失败，点击红色标记可重试`, icon: 'none', duration: 3500 })
  }
}

async function retrySingleItem(index) {
  const item = parseResult.value.items[index]
  uni.showLoading({ title: '正在重新保存...' })
  try {
    await saveSingleImageItem(item)
    const nextFailed = { ...failedItems.value }
    delete nextFailed[index]
    failedItems.value = nextFailed
    uni.hideLoading()
    uni.showToast({ title: '重试保存成功', icon: 'success' })
  } catch (e) {
    uni.hideLoading()
    const msg = e?.message || '单项保存失败，请再试'
    uni.showToast({ title: msg, icon: 'none' })
  }
}

async function saveSingleImageItem(item) {
  const staged = await stageMedia(item, parseResult.value.task_id)
  // #ifdef MP-WEIXIN
  if (staged.fileID && staged.fileID.startsWith('cloud://')) {
    return new Promise((resolve, reject) => {
      wx.cloud.downloadFile({
        fileID: staged.fileID,
        success: async (res) => {
          try {
            await saveImageToAlbum(res.tempFilePath)
            resolve()
          } catch (e) {
            reject(e)
          }
        },
        fail: reject
      })
    })
  }
  // #endif

  // #ifndef MP-WEIXIN
  downloadToDisk(staged.fileID)
  return
  // #endif

  return saveImageToAlbum(staged.fileID)
}

async function handleExportZip() {
  if (!parseResult.value || !parseResult.value.items) return
  isZipping.value = true
  try {
    const zipName = `renlink_${parseResult.value.platform}_${Date.now()}.zip`
    const res = await createZip(parseResult.value.task_id)

    // #ifdef MP-WEIXIN
    if (res.fileID && res.fileID.startsWith('cloud://')) {
      wx.cloud.downloadFile({
        fileID: res.fileID,
        success(downloadRes) {
          wx.shareFileMessage({
            filePath: downloadRes.tempFilePath,
            fileName: zipName,
            success() {
              uni.showToast({ title: '分享唤起成功', icon: 'success' })
            },
            fail() {
              uni.showToast({ title: '分享已取消', icon: 'none' })
            }
          })
        },
        fail() {
          uni.showToast({ title: '下载 ZIP 失败', icon: 'none' })
        }
      })
    } else {
      uni.showToast({ title: 'ZIP 服务准备中', icon: 'none' })
    }
    // #endif

    // #ifndef MP-WEIXIN
    downloadToDisk(res.fileID)
    uni.showToast({ title: '已开始下载 ZIP', icon: 'success' })
    // #endif
  } catch (err) {
    const msg = err?.message || '导出 ZIP 失败'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    isZipping.value = false
  }
}
function goToComplaint() {
  uni.setStorageSync("renlink_open_complaint", "1")
  uni.switchTab({
    url: "/pages/mine/mine"
  })
}
</script>

<style lang="scss" scoped>
.container {
  padding: 24rpx;
}

.clipboard-bar {
  background-color: #E8F8EE;
  border: 1rpx solid #07C160;
  border-radius: 12rpx;
  padding: 16rpx 24rpx;
  margin-bottom: 24rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .clipboard-text {
    font-size: 24rpx;
    color: #07C160;
  }

  .clipboard-actions {
    display: flex;
    align-items: center;
    gap: 16rpx;

    .btn-fill {
      background-color: #07C160;
      color: #FFFFFF;
      font-size: 22rpx;
      padding: 0 16rpx;
      height: 48rpx;
      line-height: 48rpx;
      border-radius: 24rpx;
    }

    .btn-dismiss {
      font-size: 22rpx;
      color: #7F7F7F;
    }
  }
}

.card {
  background-color: #FFFFFF;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.input-card {
  .url-textarea {
    width: 100%;
    height: 180rpx;
    font-size: 28rpx;
    line-height: 40rpx;
    color: #191919;
  }

  .placeholder-style {
    color: #B2B2B2;
  }

  .input-tools {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 20rpx;
    margin-top: 16rpx;

    .tool-btn {
      font-size: 26rpx;
      color: #7F7F7F;
    }

    .tool-btn-paste {
      background-color: #F2F3F5;
      color: #191919;
      font-size: 24rpx;
      height: 56rpx;
      line-height: 56rpx;
      border-radius: 28rpx;
    }
  }
}

.action-section {
  margin-bottom: 24rpx;

  .parse-btn {
    width: 100%;
    height: 88rpx;
    line-height: 88rpx;
    background-color: #07C160;
    color: #FFFFFF;
    font-size: 32rpx;
    font-weight: bold;
    border-radius: 44rpx;
    text-align: center;

    &.loading {
      opacity: 0.6;
    }

    &.disabled {
      background-color: #CCCCCC;
      color: #FFFFFF;
    }
  }
}

.error-banner {
  background-color: #FFF0F0;
  border-radius: 12rpx;
  padding: 16rpx 24rpx;
  margin-bottom: 24rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .error-text {
    font-size: 26rpx;
    color: #FA5151;
  }

  .error-retry-btn {
    font-size: 26rpx;
    color: #07C160;
    font-weight: bold;
  }
}

.skeleton-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 24rpx;

  .skeleton-text {
    font-size: 28rpx;
    color: #7F7F7F;
  }
}

.result-card {
  .result-header {
    margin-bottom: 20rpx;

    .tags-row {
      display: flex;
      gap: 12rpx;
      margin-bottom: 12rpx;

      .tag {
        font-size: 22rpx;
        padding: 4rpx 12rpx;
        border-radius: 6rpx;

        &.tag-platform.douyin {
          background-color: #FFF0F2;
          color: #FE2C55;
        }

        &.tag-platform.xiaohongshu {
          background-color: #FFF0F0;
          color: #FF2442;
        }

        &.tag-type {
          background-color: #E8F8EE;
          color: #07C160;
        }
      }
    }

    .result-title {
      font-size: 28rpx;
      color: #191919;
      font-weight: 500;
      line-height: 40rpx;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }

  .video-preview-box {
    position: relative;
    width: 100%;
    border-radius: 12rpx;
    overflow: hidden;
    margin-bottom: 24rpx;

    .video-cover {
      width: 100%;
      height: 380rpx;
      display: block;
      background-color: #000000;
    }

    .play-icon-overlay {
      position: absolute;
      top: 140rpx;
      left: 50%;
      transform: translateX(-50%);
      width: 80rpx;
      height: 80rpx;
      border-radius: 40rpx;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;

      .play-triangle {
        width: 0;
        height: 0;
        border-left: 24rpx solid #FFFFFF;
        border-top: 14rpx solid transparent;
        border-bottom: 14rpx solid transparent;
        margin-left: 6rpx;
      }
    }
  }

  .note-preview-box {
    .note-header-info {
      margin-bottom: 16rpx;
      .note-count {
        font-size: 24rpx;
        color: #7F7F7F;
      }
    }

    .image-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12rpx;
      margin-bottom: 24rpx;

      .grid-item {
        position: relative;
        width: 100%;
        padding-top: 100%;
        border-radius: 8rpx;
        overflow: hidden;
        background-color: #f0f0f0;

        .thumb-img {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
        }

        .item-badge {
          position: absolute;
          top: 8rpx;
          right: 8rpx;
          background: rgba(0, 0, 0, 0.6);
          color: #FFFFFF;
          font-size: 20rpx;
          padding: 2rpx 8rpx;
          border-radius: 6rpx;
        }

        .item-fail-mask {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(250, 81, 81, 0.75);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          color: #FFFFFF;

          .fail-icon {
            font-size: 32rpx;
            font-weight: bold;
          }

          .fail-retry-text {
            font-size: 22rpx;
            margin-top: 4rpx;
            text-decoration: underline;
          }
        }
      }
    }
  }

  .progress-box {
    margin-bottom: 20rpx;
    .progress-text {
      font-size: 24rpx;
      color: #07C160;
      margin-bottom: 8rpx;
      display: block;
    }
  }

  .save-actions, .note-actions {
    display: flex;
    flex-direction: column;
    gap: 16rpx;

    .save-btn {
      width: 100%;
      height: 80rpx;
      line-height: 80rpx;
      background-color: #07C160;
      color: #FFFFFF;
      font-size: 30rpx;
      border-radius: 40rpx;
    }

    .zip-btn {
      width: 100%;
      height: 80rpx;
      line-height: 80rpx;
      background-color: #FFFFFF;
      border: 2rpx solid #07C160;
      color: #07C160;
      font-size: 30rpx;
      border-radius: 40rpx;
    }
  }
}
.footer-copyright {
  margin-top: 32rpx;
  margin-bottom: 40rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16rpx;
  font-size: 22rpx;

  .copyright-text {
    color: #999999;
  }

  .complaint-link {
    color: #07C160;
    text-decoration: underline;
  }
}
</style>
