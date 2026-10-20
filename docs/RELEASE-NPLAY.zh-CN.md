# NPlay 云端编译与发布

在仓库的 **Actions → Build and release NPlay → Run workflow** 中手动启动。
工作流放在默认分支 `main`；`Use workflow from` 保持 `main`。
构建源码由表单中的 `source_ref` 指定，默认为 `main`，可填本仓库分支、标签或提交号。
选择的源码必须包含这次 NPlay 发布配置。只有你信任的源码才应使用发布凭据。

## 首次配置：六个 Repository Secrets

进入 [Settings → Secrets and variables → Actions](https://github.com/sudingquan/NPlay/settings/secrets/actions)，
添加下列机密。不要把私钥、签名文件、密码或 Base64 内容提交到仓库。

| Secret 名称 | 内容 |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | Android 发布签名 keystore 的 Base64 |
| `ANDROID_KEYSTORE_PASSWORD` | keystore 密码 |
| `ANDROID_KEY_ALIAS` | 签名密钥别名 |
| `ANDROID_KEY_PASSWORD` | 密钥密码 |
| `DIPLAY_IDENTITY_BASE64` | 已授权使用的 `identity.pk8` 的 Base64 |
| `DIPLAY_CERTIFICATE_BASE64` | 配套 `certificate.p7b` 的 Base64 |

也可以使用一键配置脚本，避免手动编码和填写六项：

1. 电脑安装 Python 3、Java JDK（提供 `keytool`）和 [GitHub CLI](https://cli.github.com/)。
2. 用 `gh auth login` 登录有本仓库管理 Secrets 权限的 GitHub 账号。
3. 在仓库根目录执行，路径改为电脑上保存的测试包：

```sh
python3 scripts/setup_release_secrets.py --auth-apk /你的路径/DiPlay-audio-test.zip
```

脚本接受包含认证材料的 APK，或含一个非 rollback APK 的 ZIP。
它复用该包的 CarPlay 认证材料，为 NPlay 创建独立 Android 签名，将六个值写入 GitHub Secrets，
不会输出秘密值。默认把签名文件和密码保存到电脑的 `~/.config/nplay-release/`。
**请备份整个文件夹；后续使用同一文件夹，不要重新生成签名。**
这个自动脚本适用于新建 NPlay 签名；已有自己的签名时，请按上表手动配置。
PKCS12 签名的密钥密码通常与 keystore 密码相同。

## 每次发布

打开 [发布工作流](https://github.com/sudingquan/NPlay/actions/workflows/release.yml)，点击 **Run workflow**：

| 参数 | 示例和说明 |
| --- | --- |
| `source_ref` | `main`，或包含发布配置的测试分支 |
| `version_name` | `0.2.21-nplay.1`，每次发布用新版本名 |
| `version_code` | 首次 `1`，以后 `2`、`3`……；覆盖升级必须递增 |
| `prerelease` | 默认勾选，发布为预览版 |

工作流会恢复凭据、编译 `:mobile:assembleRelease`、验证签名及包内认证文件，
并核对实际 APK 包名与版本。它不运行单元测试或 lint，也不代表已通过实车验证。

随后创建 `nplay-v<version_name>` 标签和 GitHub Release，指向实际编译的提交，上传：

- `NPlay-<version_name>.apk`
- `SHA256SUMS`（APK、构建信息和签名报告的 SHA-256）
- `BUILD-INFO.json`（源码提交、版本、构建记录链接）
- `SIGNATURE.txt`（公开的 APK 签名证书信息）

同样的输出会保留为 Actions artifact 14 天。已存在的 Release/标签不会被主动覆盖或移动；
发生重复版本时应填写新版本名重跑，而不是删除已有发布。

APK 使用独立包名 `com.sudingquan.nplay`，界面仍沿用 DiPlay 的应用名称。
可与官方 DiPlay 并存，不能覆盖官方版，也不会自动继承官方版或旧测试版的设置。
连接前停止另一个 DiPlay/NPlay 实例。以后同包名、同签名且更高 `version_code` 的包可覆盖更新。

CarPlay 认证材料会被装入可下载的 APK，接收者可以提取；Android 签名私钥不会装入 APK。
工作流仅手动触发，不在 PR 中使用发布凭据。修改工作流需要 GitHub 的 workflow 写入权限。

如果 fork 的 Actions 尚未开启，先在仓库 Actions 页面启用。若组织策略禁止写入，
仓库或组织管理员需要允许该工作流的 `contents: write`；发布任务用它创建 Release。

## 常见失败

- **Configure repository Actions secrets**：按报错列出的名称补齐机密。
- **Invalid Base64**：上传原文件的 Base64，不是文件路径或 ZIP 的 Base64。
- **签名/密码错误**：确认 keystore、别名和两个密码配套，不要随意换签名。
- **APK identity/version differs**：所选源码尚未包含 NPlay 发布配置，选用最新 `main`。
- **Resource not accessible by integration**：核对仓库 Actions 写入权限或 GitHub 连接的 workflow 权限。

参考：[GitHub Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)、
[手动运行工作流](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)。
