# dengluyi-arxiv-tex

TRIZa 生成的声明式站点适配器候选。
本地契约检查不等于真实网站或登录易原生安装已验收。
使用作者自己的会话，所有写动作需宿主授权。不得重试不确定的提交。
安装前复核来源和权限；checksums 不是发布者签名。

## 待完成
- 待验收：全部 pathPrefix（/login、/user、/auth、/submit）均为候选，需授权采集实际路径并收窄到具体页面；目前没有经过认证会话验证的路径。
- 待验收：全部 pageTexts 均为页面匹配候选，包括 Login、Endorsement、Author Declarations、License、Upload Files、Uploaded Files、File Check Results、Compiler、Top-level TeX file、Preview、PDF、Submission Metadata、Title、Abstract、Review Submission、Submission complete 和 Submission ID。不得将这些候选当作实际页面已出现的事实。
- 待验收：START NEW SUBMISSION、Choose File、Upload、Check Files、Accept and Continue、Confirm、Continue、Submit Article 来自所给规范中的文档标签；其实际大小写、可见名称、唯一性、页面归属和动作效果仍待确认。
- 待验收：Title、Abstract、Authors、Primary Category、Comments、Compiler、Top-level TeX file 是尚未采集的控件标签候选。需确认实际控件类型、关联标签、输入格式、分类选项，以及元数据是否分布在多个页面。
- 待验收：采集实际声明文本、许可选项和资格提示，确认各人工步骤独立匹配具体页面；不得添加覆盖整个投稿路径的宽泛人工兜底规则。
- 待验收：核实 ZIP 选择与 Upload 是否为独立动作、文件检查到编译的实际导航顺序、Confirm 的具体作用，以及网站编译完成和失败状态的可靠观察依据。
- 待验收：确认作者可在不下载文件的情况下查看网站 PDF 预览；如果当前界面必须下载才能核验，应停止并明确此运行限制。
- 待验收：以作者明确指定的源码包核对大小写、图件、样式、参考文献依赖和编译兼容性；离线检查不能替代网站文件检查及服务器编译。
- 待验收：确认宿主支持同页步骤串行完成、标题摘要填写前禁止继续、人工确认绑定稿件版本、禁止未确认提交，以及对未知页面和模糊控件立即停止。
- 待验收：确认最终提交按钮只执行一次，超时和断线不会触发自动重试；核实真实回执路径、页面文字、投稿编号和状态字段，区分暂存记录与提交后回执。
- 当前没有代码文件变更、回归测试、提交或推送记录；本交付仅为离线 JSON 候选，不代表已通过登录易运行验收。
- 独立复核修订通过本地契约后仍必须采集真实页面；不在真实账户内执行未经验证的候选。
