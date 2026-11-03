# 当前云环境与复现配置

当前环境 running/connected，HTTP 策略 unrestricted/enforced；官方数据下载已返回 HTTP 200，全年 12 月份实际下载、校验和实验完成。旧 HTTP 403 记录见 validation/network_status.md，已被 validation/network_recovered.md 取代。

install_script 保存隔离 venv 与精确 requirements-lock.txt 安装、pip check。start_skill 包含现有检出、不新建 worktree、合成/正式流程、资源限制、缓存复用、notebook、守恒核对及解释边界。没有新增 secret，没有 GitHub token 请求；代码和报告已推送 GitHub main。

当前实例的真实数据执行已验证；配置草稿保存与 UI 发布是不同操作。代理工具没有发布动作，保存草稿不等于发布新快照。以后任务如需使用最新文件/说明，需在环境设置审核、保存并发布；新任务恢复未独立验证。

最新扩展已运行并通过40项测试。历史来源/校准、天气、时长、MPC、路径、60站、第三个notebook和10页PDF的复现入口为scripts/all_research.sh；该脚本组成步骤均已逐项执行。保留source hashes，不将变化档案缺失段填成已知；原始大文件不入交付ZIP。
