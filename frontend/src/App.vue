<script>
export default {
  onLaunch: function () {
    // #ifdef MP-WEIXIN
    if (typeof wx !== 'undefined' && wx.cloud) {
      wx.cloud.init({
        traceUser: true
      })
    }
    // #endif
  },
  onShow: function () {},
  onHide: function () {}
}
</script>

<style lang="scss">
@import './uni.scss';

page {
  background-color: #F7F8FA;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  color: #191919;
  box-sizing: border-box;
}

view, text, image, textarea, button {
  box-sizing: border-box;
}
</style>
