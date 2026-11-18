# 光谱含量与修正响应事故

工程入口、精确数值、维度、发布及冻结语义沿用 README.md。只修复现有计算和报告，不增加新的分析入口。

## 已观察到的偏差

命令 `python3 -B incident.py` 使用独立的内存数据库，通过公开接纳、冻结、解混、方向和读取入口核账。每行输出输入、预期、实测及重构响应，有理数编码沿用 archive/codec.py；任一数值不符时退出 1 并输出 UNMIX_RESPONSE_MISMATCH，全部相符时退出 0 并输出 UNMIX_RESPONSE_OK。异常保持原类型，不将文件或数据库错误改写为该标记。

- A=[[1,1,0],[0,0,1]]、y=[1,0]：应为 x=[1/2,1/2,0]；当前返回 [1,0,0]。d=[0,1] 应为 h=[0,0,1]、Ah=[0,1]，当前均为零；d=[0,-1] 应为零。
- A=[[1,2]]、y=[1]、d=[1]：x 和 h 都应为 [1/5,2/5]；当前都为 [0,1/2]，虽然重构正确，含量解释仍有偏差。
- A=[[1,0],[0,1]]、y=[1,0]、d=[0,1]：父含量已正确为 [1,0]，响应应为 [0,1]，当前却为零。

父成果和方向成果均是对外交付，不得只让其中一个数值正确。方向是指定规范映射的精确右导数，不是固定有限步长差商；例如 A=[[1]]、y=[1/1000000000000]、d=[-1] 的右导数为 -1。正反方向分别处理，沿用原有零列、秩亏及有符号测量支持。

## 运行与保留

全部原测试及其断言保持不变。完整核验是 `python3 -B verify.py`，等价的原套件入口是 `python3 -B -m unittest discover -s tests -t .`；另运行 `python3 -B incident.py` 核对上述公开事故。演示仍用 `python3 -B demo.py`，展示含量、正反响应、源更正、重开及自足导出；.pointwise-runtime.json 与 RUN_MANIFEST.json 保留既有运行约定。

故障初始版本中，原套件涉及规范含量和边界响应的断言同样应暴露偏差，不能删改断言以令初始版本全绿。以下正常回归应继续通过：

```sh
python3 -B -m unittest tests.test_unmix.TestUnmix.test_unique_solution tests.test_response.TestResponse.test_invalid_parent_and_direction tests.test_lifecycle.TestLifecycle.test_channel_mismatch tests.test_lifecycle.TestLifecycle.test_invalid_intake_is_atomic tests.test_archive.TestArchive.test_publish_failure_retry tests.test_archive.TestArchive.test_codec_and_fixed_read
```

修复后恢复完整原套件和事故核账通过。补充必要独立核账及简短根因、交接不变量和实际验证说明；更正、对象隔离、持久重开、失败回滚及导出语义均以 README.md 和原断言为准。不要求新的性能、并行或恢复系统。
