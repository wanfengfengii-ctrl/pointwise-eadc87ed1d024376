# 环境光谱实验室

Python 3.11 标准库离线分析工程。仪器人员追加校准和测量修订，分析员冻结明确输入，质控员读取规范含量、单侧修正响应及自足导出。无第三方依赖。

运行：`python3 -B verify.py` 执行全部回归；`python3 -B demo.py` 在临时目录演示接纳、冻结、求解、正反方向、源更正、关闭重开和导出。demo 清理自己的数据库及导出。运行 argv 见 .pointwise-runtime.json 和 RUN_MANIFEST.json，命令从项目根目录执行。

## 一天的工作

1. 提交有序通道、组分、单位及非负校准矩阵，得到字典修订。
2. 提交有样本身份的有序测量批次，得到批次及初始修订。
3. 分析员选择明确修订，核对通道身份、顺序和单位。
4. 冻结队列保存来源和独立快照，后续源更正不改变它。
5. 逐记录解混，保存规范含量、重构和残差供解释。
6. 质控员指定已发布父成果，分别提交正向与反向仪器修正。
7. 发布系数和重构右导数，识别零组分进入；它描述微小修正。
8. 导出指定响应的完整固定父链供离线复核。更正后重新冻结生成新成果，旧成果继续可读。

## 公开 API

所有入口第一个参数为 Catalog：

```python
from spectral.archive.catalog import Catalog
from spectral.dictionary.revisions import save_dictionary
from spectral.measurements.intake import save_batch
from spectral.measurements.cohorts import freeze
from spectral.unmixing.jobs import unmix
from spectral.response.requests import direction
from spectral.archive.reading import read
from spectral.archive.export import export

c = Catalog("lab.sqlite")
try:
    d = save_dictionary(c, ["c1", "c2"], ["a", "b", "tracer"],
                        ["abs", "abs"], ["mg/L"] * 3,
                        [[1, 1, 0], [0, 0, 1]])
    b = save_batch(c, ["c1", "c2"], ["abs", "abs"],
                   [{"sample_id": "river-07", "values": [1, 0]}])
    revisions = c.read_record(b, "batch")["data"]["revision_ids"]
    q = freeze(c, d, revisions)
    p = unmix(c, q)
    r = direction(c, p, [0, 1])
    fixed = read(c, r)
    export(c, r, "quality.json")
finally:
    c.close()
```

- save_dictionary(c, channels, components, channel_units, component_units, matrix, previous=None) 返回不可变修订ID。更正传明确旧修订，旧值保留。
- save_batch(c, channels, units, records) 返回批次ID。records 为 sample_id、values 两字段对象列表。读取批次负载的 revision_ids 按提交顺序取得明确修订。
- append_measurement_revision(c, previous, values, channels=None, units=None) 位于 measurements/revisions.py，返回更正修订ID；省略坐标沿用旧修订。
- freeze(c, dictionary_id, measurement_ids) 返回固定队列ID。不能同时选择同一样本的多个修订；记录身份为 (batch_id,sample_id)，不同批次可有同名样本。
- unmix(c, cohort_id, fail_at=None) 返回解混成果ID；direction(c, parent_id, values, fail_at=None) 返回方向成果ID。同一方向作用于父队列全部记录，正反方向分别调用。
- read(c, artifact_id) 返回独立解码的 id、kind、parents、data。解混 data 有 cohort_id、input、rows；行按输入顺序保存 sample_id、measurement_revision、coefficients、reconstruction、residual_squared。方向 data 保存 parent_id、cohort_id、方向、坐标、单位及 rows，行的 coefficients 为 h、reconstruction 为 Ah。
- export(c, direction_id, destination) 返回目标 Path；父目录须已存在。包格式版本1，chain 内有 artifacts、records，明确引用构成完整父链。
- Catalog.initialize() 可重复执行，保留更正、指针和成果。close 后重开保留历史。一个队列对应一个逻辑解混，一个父成果和精确方向对应一个逻辑响应，稳定重试不重复发布。

## 计算与数据

有序目录、矩阵行、记录、向量等使用 list 或 tuple。1～24 通道、1～10 组分；A 非负，允许零列、重复列、比例列及秩亏；y、d 可带符号。数字接受 Fraction、非布尔 int、精确分数字符串和有限十进制字符串。拒绝 float、bool、None、非法值、缺失元素、空批次及重复身份。运算和保存均为精确 Fraction，无容差、随机性或隐式单位换算。

按声明含量单位的数值坐标，先最小化残差平方和，再在全部非负残差最优点中最小化系数平方范数。全零字典返回零系数。方向返回指定 d 的右导数 h 及 Ah；允许零组分进入，不假定正反方向互为相反数。有限面枚举的成本随组分数指数增长，没有速度或并行承诺。

核账：A=[[1,1,0],[0,0,1]]、y=[1,0] 得 x=[1/2,1/2,0]；d=[0,1] 得 h=[0,0,1]，反方向得零。比例列 [1,2] 在 y=1 时为 [1/5,2/5]。A=[[1,1],[0,1]]、y=[0,1] 得 [0,1/2]，残差平方和1/2。

## 失败及复核

非法业务值抛 ValueError，未知修订、队列或成果抛 KeyError；文件及数据库异常保持原类型。失败整次拒绝，不产生成功记录，不用最新源代替未知身份。SQLite 同事务提交负载及可见目录；fail_at 可取 after_payload 或 after_index，抛 RuntimeError 以核验普通发布失败的回滚及稳定重试，不模拟进程崩溃。

读取和导出不导入求解器，不重新计算。修改读取对象不会污染后续读取。导出写入同目录临时文件，完整写入并 fsync 后原子替换；失败清理本次临时文件，保留原目标与数据库成果，无额外成功标记。有理数编码为 {"$fraction":[分子,正分母]}，约分形式唯一；archive/codec.py 的 decode_payload 可恢复。包内含来源、顺序、单位、A、y、d、x、Ax、残差、h、Ah，脱离数据库可核对。

四个测试文件覆盖手算、独立行列式与分层投影核账、精确右参数区间、坐标拒绝、冻结后更正、对象隔离、持久重开、重复初始化、发布失败重试和导出失败。POINTWISE_SCENARIO 行在真实断言后打印独立预期、实测及下游值，不替代完整回归。
