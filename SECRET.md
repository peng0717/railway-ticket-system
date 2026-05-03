# 铁路售票系统 - 敏感配置信息

## 邮件服务配置

### QQ邮箱SMTP配置
- **SMTP服务器**: smtp.qq.com
- **SMTP端口**: 465 (SSL)
- **邮箱账号**: 2790885462@qq.com
- **授权码**: fncwiptujvaydhba
- **发件人名称**: 铁路客票系统

### 环境变量配置
可以通过以下环境变量覆盖默认配置：

```bash
export MAIL_SMTP_SERVER="smtp.qq.com"
export MAIL_SMTP_PORT="465"
export MAIL_SENDER="2790885462@qq.com"
export MAIL_PASSWORD="fncwiptujvaydhba"
export MAIL_SENDER_NAME="铁路客票系统"
export MAIL_ENABLED="true"
```

### 注意事项
1. 授权码是QQ邮箱的SMTP专用密码，不是登录密码
2. 邮件功能默认启用，如需关闭可设置 `MAIL_ENABLED=false`
3. 邮件发送失败时会自动fallback到开发模式，在页面显示验证码
