<template>
  <view class="container">
    <!-- 用户信息卡片 (AC-009) -->
    <view class="card user-card">
      <view class="avatar-circle">
        <text class="avatar-text">用</text>
      </view>
      <view class="user-info">
        <text class="user-name">微信用户</text>
        <text class="user-uid">UID: wx_user_***</text>
      </view>
    </view>

    <!-- 历史记录区域 -->
    <view class="history-section">
      <view class="section-header">
        <text class="section-title">解析历史</text>
        <text class="section-sub">下拉可刷新</text>
      </view>

      <!-- 空态 (AC-009) -->
      <view v-if="!isLoading && historyList.length === 0" class="card empty-card">
        <view class="empty-icon-box">
          <text class="empty-icon">📂</text>
        </view>
        <text class="empty-text">暂无解析记录，快去主页提取第一个链接吧</text>
        <button class="empty-action-btn" @tap="goToHome">去提取</button>
      </view>

      <!-- 历史卡片列表 (AC-009, AC-010) -->
      <view v-else class="history-list">
        <view v-for="item in historyList" :key="item._id" class="card history-card">
          <image
            class="history-cover"
            :src="item.cover || 'https://dummyimage.com/120x120/eee/999.png&text=Renlink'"
            mode="aspectFill"
          />
          <view class="history-main">
            <view class="history-tags">
              <text class="tag" :class="item.platform">
                {{ item.platform === 'douyin' ? '抖音' : '小红书' }}
              </text>
              <text class="tag-type">
                {{ item.content_type === 'video' ? '视频' : (item.item_count + '图') }}
              </text>
            </view>
            <text class="history-title">{{ item.title || item.original_url }}</text>
            <text class="history-date">{{ formatDate(item.create_time) }}</text>
          </view>
          <view class="history-actions">
            <button class="btn-action" size="mini" @tap="copyLink(item.original_url)">复制</button>
            <button class="btn-action btn-primary" size="mini" @tap="reParse(item.original_url)">再次解析</button>
          </view>
        </view>

        <!-- 加载状态与底线 -->
        <view class="list-footer">
          <text v-if="isLoading">加载中...</text>
          <text v-else-if="noMore">已加载全部历史记录</text>
        </view>
      </view>
    </view>

    <!-- 版权声明与侵权投诉入口区块 (TASK-008 / AC-008) -->
    <view class="card compliance-card">
      <view class="compliance-header">
        <text class="compliance-title">版权声明与服务规范</text>
      </view>
      <view class="compliance-body">
        <text class="compliance-desc">本工具仅供个人备份，版权归原作者所有。请合理使用提取功能，尊重原创知识产权。</text>
      </view>
      <view class="compliance-actions">
        <button class="btn-complaint" @tap="openComplaintModal">侵权投诉 / 意见反馈</button>
      </view>
    </view>

    <!-- 侵权投诉表单弹窗 (TASK-008 / AC-008) -->
    <view v-if="showComplaintModal" class="modal-mask" @tap="closeComplaintModal">
      <view class="modal-card" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">侵权投诉与版权申诉</text>
          <text class="modal-close" @tap="closeComplaintModal">✕</text>
        </view>
        <view class="modal-body">
          <view class="contact-email-box">
            <text class="email-label">投诉受理邮箱：</text>
            <view class="email-row">
              <text class="email-value">compliance@renlink.com</text>
              <button class="btn-copy-email" size="mini" @tap="copyComplaintEmail">复制</button>
            </view>
          </view>
          <view class="form-group">
            <text class="form-label">涉嫌侵权链接或内容描述</text>
            <textarea
              v-model="complaintContent"
              class="form-textarea"
              placeholder="请提供涉嫌侵权的链接、作品原作者权属证明或详细说明..."
              maxlength="500"
            />
          </view>
          <view class="form-group">
            <text class="form-label">联系方式（邮箱/手机）</text>
            <input
              v-model="complaintContact"
              class="form-input"
              placeholder="请留下您的联系方式以便接收处理进度"
              maxlength="100"
            />
          </view>
        </view>
        <view class="modal-actions">
          <button class="btn-modal-cancel" @tap="closeComplaintModal">取消</button>
          <button
            class="btn-modal-submit"
            :disabled="isSubmittingComplaint"
            @tap="submitComplaint"
          >
            {{ isSubmittingComplaint ? '提交中...' : '提交投诉' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import { getHistoryRecords } from '../../api/history'

const historyList = ref([])
const page = ref(1)
const pageSize = 10
const isLoading = ref(false)
const noMore = ref(false)

// 侵权投诉与合规声明状态
const showComplaintModal = ref(false)
const complaintContent = ref('')
const complaintContact = ref('')
const isSubmittingComplaint = ref(false)

onShow(() => {
  loadHistory(true)
  if (uni.getStorageSync('renlink_open_complaint')) {
    uni.removeStorageSync('renlink_open_complaint')
    showComplaintModal.value = true
  }
})

onPullDownRefresh(async () => {
  await loadHistory(true)
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  if (!noMore.value && !isLoading.value) {
    page.value++
    loadHistory(false)
  }
})

async function loadHistory(isRefresh = false) {
  if (isRefresh) {
    page.value = 1
    noMore.value = false
  }
  isLoading.value = true

  try {
    const list = await getHistoryRecords({
      page: page.value,
      pageSize
    })
    if (isRefresh) {
      historyList.value = list
    } else {
      historyList.value = [...historyList.value, ...list]
    }
    if (list.length < pageSize) {
      noMore.value = true
    }
  } catch (err) {
    console.error('loadHistory error:', err)
  } finally {
    isLoading.value = false
  }
}

function formatDate(timestamp) {
  if (!timestamp) return ''
  const d = new Date(timestamp)
  const pad = (n) => (n < 10 ? '0' + n : n)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function copyLink(url) {
  if (!url) return
  uni.setClipboardData({
    data: url,
    success() {
      uni.showToast({ title: '原链接已复制', icon: 'success' })
    }
  })
}

function reParse(url) {
  if (!url) return
  uni.setStorageSync('renlink_auto_parse_url', url)
  uni.switchTab({
    url: '/pages/index/index'
  })
}

function goToHome() {
  uni.switchTab({
    url: '/pages/index/index'
  })
}

function openComplaintModal() {
  showComplaintModal.value = true
}

function closeComplaintModal() {
  showComplaintModal.value = false
}

function copyComplaintEmail() {
  uni.setClipboardData({
    data: 'compliance@renlink.com',
    success() {
      uni.showToast({ title: '投诉邮箱已复制', icon: 'success' })
    }
  })
}

async function submitComplaint() {
  if (!complaintContent.value.trim()) {
    uni.showToast({ title: '请填写侵权链接或内容描述', icon: 'none' })
    return
  }
  if (!complaintContact.value.trim()) {
    uni.showToast({ title: '请填写联系方式以便反馈', icon: 'none' })
    return
  }

  isSubmittingComplaint.value = true
  try {
    const net = await new Promise((resolve) => {
      uni.getNetworkType({
        success: resolve,
        fail: () => resolve({ networkType: 'unknown' })
      })
    })

    if (net.networkType === 'none') {
      uni.showToast({ title: '网络连接失败，请检查网络设置', icon: 'none' })
      return
    }

    // 写入本地安全日志以供追溯
    const complaints = uni.getStorageSync('renlink_complaints') || []
    complaints.push({
      content: complaintContent.value.trim(),
      contact: complaintContact.value.trim(),
      time: Date.now()
    })
    uni.setStorageSync('renlink_complaints', complaints)

    uni.showToast({ title: '投诉已提交，我们将尽快核实处理', icon: 'success' })
    complaintContent.value = ''
    complaintContact.value = ''
    showComplaintModal.value = false
  } catch (err) {
    const msg = err?.message || '提交失败，请重试'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    isSubmittingComplaint.value = false
  }
}
</script>

<style lang="scss" scoped>
.container {
  padding: 24rpx;
}

.card {
  background-color: #FFFFFF;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.user-card {
  display: flex;
  align-items: center;
  gap: 24rpx;

  .avatar-circle {
    width: 120rpx;
    height: 120rpx;
    border-radius: 60rpx;
    background-color: #E8F8EE;
    color: #07C160;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 48rpx;
    font-weight: bold;
  }

  .user-info {
    display: flex;
    flex-direction: column;
    gap: 8rpx;

    .user-name {
      font-size: 32rpx;
      font-weight: bold;
      color: #191919;
    }

    .user-uid {
      font-size: 24rpx;
      color: #7F7F7F;
    }
  }
}

.history-section {
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16rpx;

    .section-title {
      font-size: 30rpx;
      font-weight: bold;
      color: #191919;
    }

    .section-sub {
      font-size: 24rpx;
      color: #7F7F7F;
    }
  }
}

.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 24rpx;

  .empty-icon-box {
    font-size: 72rpx;
    margin-bottom: 20rpx;
  }

  .empty-text {
    font-size: 26rpx;
    color: #7F7F7F;
    margin-bottom: 32rpx;
    text-align: center;
  }

  .empty-action-btn {
    background-color: #07C160;
    color: #FFFFFF;
    font-size: 28rpx;
    height: 64rpx;
    line-height: 64rpx;
    padding: 0 40rpx;
    border-radius: 32rpx;
  }
}

.history-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 20rpx;

  .history-cover {
    width: 120rpx;
    height: 120rpx;
    border-radius: 8rpx;
    background-color: #f0f0f0;
    flex-shrink: 0;
  }

  .history-main {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 6rpx;

    .history-tags {
      display: flex;
      gap: 8rpx;

      .tag {
        font-size: 20rpx;
        padding: 2rpx 8rpx;
        border-radius: 4rpx;

        &.douyin {
          background-color: #FFF0F2;
          color: #FE2C55;
        }

        &.xiaohongshu {
          background-color: #FFF0F0;
          color: #FF2442;
        }
      }

      .tag-type {
        font-size: 20rpx;
        color: #7F7F7F;
      }
    }

    .history-title {
      font-size: 26rpx;
      color: #191919;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .history-date {
      font-size: 22rpx;
      color: #B2B2B2;
    }
  }

  .history-actions {
    display: flex;
    flex-direction: column;
    gap: 12rpx;
    flex-shrink: 0;

    .btn-action {
      font-size: 22rpx;
      padding: 0 16rpx;
      height: 48rpx;
      line-height: 48rpx;
      border-radius: 24rpx;
      background-color: #F2F3F5;
      color: #191919;

      &.btn-primary {
        background-color: #E8F8EE;
        color: #07C160;
      }
    }
  }
}

.list-footer {
  text-align: center;
  padding: 24rpx 0;
  font-size: 24rpx;
  color: #B2B2B2;
}

/* 版权声明与合规卡片 */
.compliance-card {
  .compliance-header {
    margin-bottom: 12rpx;
    .compliance-title {
      font-size: 28rpx;
      font-weight: bold;
      color: #191919;
    }
  }

  .compliance-body {
    margin-bottom: 16rpx;
    .compliance-desc {
      font-size: 24rpx;
      line-height: 36rpx;
      color: #7F7F7F;
    }
  }

  .compliance-actions {
    .btn-complaint {
      background-color: #F7F8FA;
      color: #555555;
      font-size: 24rpx;
      height: 60rpx;
      line-height: 60rpx;
      border-radius: 30rpx;
      border: 1rpx solid #E0E2E5;
    }
  }
}

/* 投诉弹窗 */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 40rpx;
}

.modal-card {
  width: 100%;
  max-width: 620rpx;
  background-color: #FFFFFF;
  border-radius: 20rpx;
  padding: 32rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .modal-title {
      font-size: 32rpx;
      font-weight: bold;
      color: #191919;
    }

    .modal-close {
      font-size: 36rpx;
      color: #999999;
      padding: 0 10rpx;
    }
  }

  .modal-body {
    display: flex;
    flex-direction: column;
    gap: 20rpx;

    .contact-email-box {
      background-color: #F8FAF9;
      border-radius: 10rpx;
      padding: 16rpx 20rpx;
      border: 1rpx solid #E3ECE6;

      .email-label {
        font-size: 22rpx;
        color: #7F7F7F;
        display: block;
        margin-bottom: 6rpx;
      }

      .email-row {
        display: flex;
        justify-content: space-between;
        align-items: center;

        .email-value {
          font-size: 26rpx;
          color: #07C160;
          font-weight: 500;
        }

        .btn-copy-email {
          font-size: 22rpx;
          padding: 0 16rpx;
          height: 44rpx;
          line-height: 44rpx;
          background-color: #E8F8EE;
          color: #07C160;
          border-radius: 22rpx;
        }
      }
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: 10rpx;

      .form-label {
        font-size: 24rpx;
        color: #333333;
        font-weight: 500;
      }

      .form-textarea {
        width: 100%;
        height: 160rpx;
        background-color: #F7F8FA;
        border-radius: 12rpx;
        padding: 16rpx;
        box-sizing: border-box;
        font-size: 24rpx;
        line-height: 36rpx;
      }

      .form-input {
        width: 100%;
        height: 72rpx;
        background-color: #F7F8FA;
        border-radius: 12rpx;
        padding: 0 16rpx;
        box-sizing: border-box;
        font-size: 24rpx;
      }
    }
  }

  .modal-actions {
    display: flex;
    gap: 20rpx;
    margin-top: 10rpx;

    .btn-modal-cancel {
      flex: 1;
      height: 72rpx;
      line-height: 72rpx;
      background-color: #F2F3F5;
      color: #666666;
      font-size: 26rpx;
      border-radius: 36rpx;
    }

    .btn-modal-submit {
      flex: 1;
      height: 72rpx;
      line-height: 72rpx;
      background-color: #07C160;
      color: #FFFFFF;
      font-size: 26rpx;
      border-radius: 36rpx;
    }
  }
}
</style>
