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

onShow(() => {
  loadHistory(true)
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
</style>
