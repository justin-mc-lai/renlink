/**
 * 相册权限与保存工具库
 */

/**
 * 检查并申请相册写入权限（AC-008）
 * 首次拒绝后再次触发时弹出模态确认弹窗，引导打开 openSetting
 * @returns {Promise<boolean>}
 */
export async function ensureAlbumPermission() {
  // #ifdef MP-WEIXIN
  return new Promise((resolve) => {
    wx.getSetting({
      success(res) {
        if (res.authSetting['scope.writePhotosAlbum'] === undefined) {
          // 首次申请
          wx.authorize({
            scope: 'scope.writePhotosAlbum',
            success() {
              resolve(true)
            },
            fail() {
              resolve(false)
            }
          })
        } else if (res.authSetting['scope.writePhotosAlbum'] === false) {
          // 已被拒绝，弹窗引导用户手动开启
          wx.showModal({
            title: '需要相册权限',
            content: '需要相册权限才能将视频/图片保存到手机',
            confirmText: '去设置',
            cancelText: '取消',
            success(modalRes) {
              if (modalRes.confirm) {
                wx.openSetting({
                  success(settingRes) {
                    if (settingRes.authSetting['scope.writePhotosAlbum']) {
                      resolve(true)
                    } else {
                      resolve(false)
                    }
                  },
                  fail() {
                    resolve(false)
                  }
                })
              } else {
                resolve(false)
              }
            }
          })
        } else {
          // 已经有权限
          resolve(true)
        }
      },
      fail() {
        resolve(false)
      }
    })
  })
  // #endif

  // #ifndef MP-WEIXIN
  return true
  // #endif
}

/**
 * 保存单个视频到系统相册
 * @param {string} filePath 本地临时路径或云存储下载路径
 * @returns {Promise<void>}
 */
export async function saveVideoToAlbum(filePath) {
  // #ifdef MP-WEIXIN
  return new Promise((resolve, reject) => {
    wx.saveVideoToPhotosAlbum({
      filePath,
      success() {
        resolve()
      },
      fail(err) {
        reject(err)
      }
    })
  })
  // #endif

  // #ifndef MP-WEIXIN
  window.open(filePath, '_blank')
  return Promise.resolve()
  // #endif
}

/**
 * 保存单张图片到系统相册
 * @param {string} filePath 本地临时路径
 * @returns {Promise<void>}
 */
export async function saveImageToAlbum(filePath) {
  // #ifdef MP-WEIXIN
  return new Promise((resolve, reject) => {
    wx.saveImageToPhotosAlbum({
      filePath,
      success() {
        resolve()
      },
      fail(err) {
        reject(err)
      }
    })
  })
  // #endif

  // #ifndef MP-WEIXIN
  window.open(filePath, '_blank')
  return Promise.resolve()
  // #endif
}
