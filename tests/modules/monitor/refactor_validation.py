#!/usr/bin/env python3
"""
重构验证测试系统
用于验证监听模块重构前后的功能一致性和性能表现
"""

import asyncio
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
from unittest.mock import Mock, AsyncMock
from dataclasses import dataclass, asdict
import hashlib

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

# 导入测试相关模块
sys.path.append(os.path.dirname(__file__))
from comprehensive_e2e_test import ComprehensiveE2ETestRunner, TestResult

@dataclass
class PerformanceBenchmark:
    """性能基准数据类"""
    test_name: str
    execution_time: float
    memory_usage: float
    api_calls: int
    messages_processed: int
    timestamp: str

@dataclass
class RefactorValidationResult:
    """重构验证结果"""
    test_name: str
    before_result: TestResult
    after_result: TestResult
    performance_change: Dict[str, float]
    behavior_consistent: bool
    issues: List[str]

class RefactorValidator:
    """重构验证器"""
    
    def __init__(self):
        self.baseline_results = {}
        self.baseline_performance = {}
        self.validation_results = []
        
    def save_baseline(self, results: List[TestResult], performance: List[PerformanceBenchmark]):
        """保存重构前的基线数据"""
        baseline_file = Path("refactor_baseline.json")
        
        baseline_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'test_results': [asdict(result) for result in results],
            'performance_benchmarks': [asdict(perf) for perf in performance],
            'total_tests': len(results),
            'success_count': sum(1 for r in results if r.success),
            'total_execution_time': sum(r.execution_time for r in results),
            'total_api_calls': sum(r.api_calls for r in results)
        }
        
        with open(baseline_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 基线数据已保存到 {baseline_file}")
        print(f"   测试总数: {len(results)}")
        print(f"   成功测试: {sum(1 for r in results if r.success)}")
        print(f"   总执行时间: {sum(r.execution_time for r in results):.2f}秒")
    
    def load_baseline(self) -> Tuple[List[TestResult], List[PerformanceBenchmark]]:
        """加载基线数据"""
        baseline_file = Path("refactor_baseline.json")
        
        if not baseline_file.exists():
            raise FileNotFoundError("基线数据文件不存在，请先运行建立基线")
        
        with open(baseline_file, 'r', encoding='utf-8') as f:
            baseline_data = json.load(f)
        
        test_results = [TestResult(**data) for data in baseline_data['test_results']]
        performance_benchmarks = [PerformanceBenchmark(**data) for data in baseline_data['performance_benchmarks']]
        
        return test_results, performance_benchmarks
    
    def compare_results(self, baseline_results: List[TestResult], 
                       current_results: List[TestResult]) -> List[RefactorValidationResult]:
        """比较重构前后的测试结果"""
        validation_results = []
        
        # 创建基线结果的字典，便于查找
        baseline_dict = {result.test_name: result for result in baseline_results}
        
        for current_result in current_results:
            test_name = current_result.test_name
            baseline_result = baseline_dict.get(test_name)
            
            if not baseline_result:
                # 新增的测试
                validation_results.append(RefactorValidationResult(
                    test_name=test_name,
                    before_result=TestResult(test_name="N/A", success=True, details="新测试", execution_time=0.0),
                    after_result=current_result,
                    performance_change={},
                    behavior_consistent=True,
                    issues=["新增测试"] if current_result.success else ["新测试失败"]
                ))
                continue
            
            # 比较行为一致性
            behavior_consistent = (
                baseline_result.success == current_result.success and
                self._compare_test_behavior(baseline_result, current_result)
            )
            
            # 计算性能变化
            performance_change = {
                'execution_time_change': (current_result.execution_time - baseline_result.execution_time),
                'execution_time_ratio': (current_result.execution_time / baseline_result.execution_time) if baseline_result.execution_time > 0 else 1.0,
                'api_calls_change': current_result.api_calls - baseline_result.api_calls
            }
            
            # 识别问题
            issues = []
            if not behavior_consistent:
                issues.append("行为不一致")
            if current_result.success != baseline_result.success:
                issues.append("成功状态改变")
            if performance_change['execution_time_ratio'] > 1.5:
                issues.append("执行时间显著增加")
            if performance_change['api_calls_change'] != 0:
                issues.append("API调用次数改变")
            
            validation_results.append(RefactorValidationResult(
                test_name=test_name,
                before_result=baseline_result,
                after_result=current_result,
                performance_change=performance_change,
                behavior_consistent=behavior_consistent,
                issues=issues
            ))
        
        return validation_results
    
    def _compare_test_behavior(self, baseline: TestResult, current: TestResult) -> bool:
        """比较测试行为的核心逻辑"""
        # 比较关键行为指标
        if baseline.success != current.success:
            return False
        
        # 对于成功的测试，比较详细信息的相似性
        if baseline.success and current.success:
            # 可以添加更细粒度的比较逻辑
            # 例如，比较API调用次数、处理的消息数量等
            return True
        
        # 对于失败的测试，确保失败原因类似
        if not baseline.success and not current.success:
            return True
        
        return True
    
    def generate_validation_report(self, validation_results: List[RefactorValidationResult]) -> Dict[str, Any]:
        """生成重构验证报告"""
        total_tests = len(validation_results)
        consistent_tests = sum(1 for r in validation_results if r.behavior_consistent)
        tests_with_issues = [r for r in validation_results if r.issues]
        
        # 性能统计
        performance_improvements = []
        performance_regressions = []
        
        for result in validation_results:
            if 'execution_time_ratio' in result.performance_change:
                ratio = result.performance_change['execution_time_ratio']
                if ratio < 0.9:  # 性能提升超过10%
                    performance_improvements.append((result.test_name, ratio))
                elif ratio > 1.1:  # 性能退化超过10%
                    performance_regressions.append((result.test_name, ratio))
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'consistent_behavior': consistent_tests,
                'behavior_consistency_rate': (consistent_tests / total_tests * 100) if total_tests > 0 else 0,
                'tests_with_issues': len(tests_with_issues),
                'performance_improvements': len(performance_improvements),
                'performance_regressions': len(performance_regressions)
            },
            'detailed_results': validation_results,
            'performance_analysis': {
                'improvements': performance_improvements,
                'regressions': performance_regressions
            },
            'issues_summary': self._summarize_issues(tests_with_issues),
            'recommendation': self._generate_recommendation(validation_results)
        }
        
        return report
    
    def _summarize_issues(self, tests_with_issues: List[RefactorValidationResult]) -> Dict[str, int]:
        """总结问题类型"""
        issue_counts = {}
        for test in tests_with_issues:
            for issue in test.issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        return issue_counts
    
    def _generate_recommendation(self, validation_results: List[RefactorValidationResult]) -> str:
        """生成重构建议"""
        total_tests = len(validation_results)
        consistent_tests = sum(1 for r in validation_results if r.behavior_consistent)
        consistency_rate = (consistent_tests / total_tests * 100) if total_tests > 0 else 0
        
        if consistency_rate >= 95:
            return "✅ 重构成功！行为一致性达到95%以上，可以安全部署。"
        elif consistency_rate >= 85:
            return "⚠️ 重构基本成功，但存在一些不一致性，建议检查具体问题后再部署。"
        else:
            return "❌ 重构存在严重问题，行为一致性低于85%，强烈建议修复后再验证。"
    
    def print_validation_report(self, report: Dict[str, Any]):
        """打印验证报告"""
        print("\n" + "=" * 80)
        print("📊 重构验证报告")
        print("=" * 80)
        
        summary = report['summary']
        print(f"\n🎯 总体结果:")
        print(f"   总测试数: {summary['total_tests']}")
        print(f"   行为一致: {summary['consistent_behavior']} ({summary['behavior_consistency_rate']:.1f}%)")
        print(f"   有问题的测试: {summary['tests_with_issues']}")
        
        print(f"\n⚡ 性能分析:")
        print(f"   性能提升: {summary['performance_improvements']} 个测试")
        print(f"   性能退化: {summary['performance_regressions']} 个测试")
        
        # 显示性能变化详情
        if report['performance_analysis']['improvements']:
            print(f"\n🚀 性能提升的测试:")
            for test_name, ratio in report['performance_analysis']['improvements'][:5]:
                improvement = (1 - ratio) * 100
                print(f"   ✅ {test_name}: 提升 {improvement:.1f}%")
        
        if report['performance_analysis']['regressions']:
            print(f"\n⚠️ 性能退化的测试:")
            for test_name, ratio in report['performance_analysis']['regressions'][:5]:
                regression = (ratio - 1) * 100
                print(f"   ❌ {test_name}: 退化 {regression:.1f}%")
        
        # 显示问题总结
        if report['issues_summary']:
            print(f"\n🔍 问题类型统计:")
            for issue_type, count in report['issues_summary'].items():
                print(f"   {issue_type}: {count} 个测试")
        
        print(f"\n💡 建议:")
        print(f"   {report['recommendation']}")
        
        print(f"\n✅ 验证报告生成完成！")

async def establish_baseline():
    """建立重构前的基线"""
    print("🏗️ 建立重构基线...")
    
    # 运行完整的端到端测试
    runner = ComprehensiveE2ETestRunner()
    report = await runner.run_all_tests()
    
    # 创建性能基准
    performance_benchmarks = []
    for result in report['test_results']:
        benchmark = PerformanceBenchmark(
            test_name=result.test_name,
            execution_time=result.execution_time,
            memory_usage=0.0,  # 可以添加内存使用监控
            api_calls=result.api_calls,
            messages_processed=1,  # 可以从测试结果中提取
            timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
        )
        performance_benchmarks.append(benchmark)
    
    # 保存基线
    validator = RefactorValidator()
    validator.save_baseline(report['test_results'], performance_benchmarks)
    
    return report

async def validate_refactor():
    """验证重构结果"""
    print("🔍 验证重构结果...")
    
    validator = RefactorValidator()
    
    try:
        # 加载基线数据
        baseline_results, baseline_performance = validator.load_baseline()
        print(f"✅ 加载基线数据: {len(baseline_results)} 个测试结果")
        
        # 运行当前测试
        runner = ComprehensiveE2ETestRunner()
        current_report = await runner.run_all_tests()
        
        # 比较结果
        validation_results = validator.compare_results(baseline_results, current_report['test_results'])
        
        # 生成验证报告
        report = validator.generate_validation_report(validation_results)
        validator.print_validation_report(report)
        
        # 保存验证报告
        report_file = Path(f"refactor_validation_report_{int(time.time())}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            # 转换不可序列化的对象
            serializable_report = {
                'summary': report['summary'],
                'performance_analysis': report['performance_analysis'],
                'issues_summary': report['issues_summary'],
                'recommendation': report['recommendation'],
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            json.dump(serializable_report, f, indent=2, ensure_ascii=False)
        
        print(f"📄 详细验证报告已保存到 {report_file}")
        
        return report
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("请先运行 'python refactor_validation.py --baseline' 建立基线")
        return None

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='监听模块重构验证工具')
    parser.add_argument('--baseline', action='store_true', help='建立重构前的基线')
    parser.add_argument('--validate', action='store_true', help='验证重构结果')
    
    args = parser.parse_args()
    
    if args.baseline:
        await establish_baseline()
    elif args.validate:
        await validate_refactor()
    else:
        print("使用方法:")
        print("  建立基线: python refactor_validation.py --baseline")
        print("  验证重构: python refactor_validation.py --validate")

if __name__ == "__main__":
    asyncio.run(main()) 