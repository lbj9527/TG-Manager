#!/usr/bin/env python3
"""
监听模块测试运行器
自动化测试执行、报告生成和结果分析
"""

import sys
import argparse
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Any


class TestRunner:
    """测试运行器类"""
    
    def __init__(self, test_dir: Path = None):
        self.test_dir = test_dir or Path(__file__).parent
        self.results = {}
        
    def run_unit_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """运行单元测试"""
        print("🔧 运行单元测试...")
        
        cmd = [
            "pytest", 
            str(self.test_dir / "test_monitor_comprehensive.py"),
            "-m", "unit",
            "--json-report", "--json-report-file=unit_results.json"
        ]
        
        if verbose:
            cmd.extend(["-v", "-s"])
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': self._extract_duration(result.stdout)
        }
    
    def run_integration_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """运行集成测试"""
        print("🔗 运行集成测试...")
        
        cmd = [
            "pytest",
            str(self.test_dir / "test_monitor_comprehensive.py"),
            "-m", "integration",
            "--json-report", "--json-report-file=integration_results.json"
        ]
        
        if verbose:
            cmd.extend(["-v", "-s"])
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': self._extract_duration(result.stdout)
        }
    
    def run_performance_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """运行性能测试"""
        print("⚡ 运行性能测试...")
        
        cmd = [
            "pytest",
            str(self.test_dir / "test_performance.py"),
            "-m", "performance",
            "--json-report", "--json-report-file=performance_results.json"
        ]
        
        if verbose:
            cmd.extend(["-v", "-s"])
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': self._extract_duration(result.stdout)
        }
    
    def run_coverage_analysis(self) -> Dict[str, Any]:
        """运行覆盖率分析"""
        print("📊 生成覆盖率报告...")
        
        cmd = [
            "pytest",
            str(self.test_dir),
            "--cov=src/modules/monitor",
            "--cov-report=html",
            "--cov-report=json",
            "--cov-report=term-missing"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 尝试读取覆盖率JSON报告
        coverage_data = {}
        try:
            with open("coverage.json", "r") as f:
                coverage_data = json.load(f)
        except FileNotFoundError:
            print("⚠️ 覆盖率报告文件未找到")
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'coverage_data': coverage_data
        }
    
    def run_smoke_tests(self) -> Dict[str, Any]:
        """运行冒烟测试（快速验证）"""
        print("💨 运行冒烟测试...")
        
        cmd = [
            "pytest",
            str(self.test_dir),
            "-m", "smoke",
            "--tb=short",
            "-q"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': self._extract_duration(result.stdout)
        }
    
    def run_specific_tests(self, test_pattern: str, verbose: bool = False) -> Dict[str, Any]:
        """运行特定的测试"""
        print(f"🎯 运行特定测试: {test_pattern}")
        
        cmd = [
            "pytest",
            str(self.test_dir),
            "-k", test_pattern
        ]
        
        if verbose:
            cmd.extend(["-v", "-s"])
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': self._extract_duration(result.stdout)
        }
    
    def run_all_tests(self, verbose: bool = False, include_slow: bool = False) -> Dict[str, Any]:
        """运行所有测试"""
        print("🚀 运行完整测试套件...")
        
        cmd = ["pytest", str(self.test_dir)]
        
        if not include_slow:
            cmd.extend(["-m", "not slow"])
            
        if verbose:
            cmd.extend(["-v", "-s"])
        else:
            cmd.append("-q")
            
        cmd.extend([
            "--json-report", "--json-report-file=all_results.json",
            "--tb=short"
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': self._extract_duration(result.stdout)
        }
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """生成测试报告"""
        report = ["=" * 60]
        report.append("📋 监听模块测试报告")
        report.append("=" * 60)
        report.append(f"⏰ 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        total_passed = 0
        total_failed = 0
        total_duration = 0
        
        for test_type, result in results.items():
            if test_type == 'summary':
                continue
                
            report.append(f"## {test_type.replace('_', ' ').title()}")
            
            if result['returncode'] == 0:
                report.append("✅ 状态: 通过")
            else:
                report.append("❌ 状态: 失败")
            
            if 'duration' in result and result['duration']:
                report.append(f"⏱️ 用时: {result['duration']}")
                total_duration += float(result['duration'].replace('s', ''))
            
            # 尝试从输出中提取测试统计
            stats = self._extract_test_stats(result['stdout'])
            if stats:
                report.append(f"📈 统计: {stats['passed']} 通过, {stats['failed']} 失败")
                total_passed += stats['passed']
                total_failed += stats['failed']
            
            if result['stderr']:
                report.append("⚠️ 错误输出:")
                report.append(result['stderr'][:500] + "..." if len(result['stderr']) > 500 else result['stderr'])
            
            report.append("")
        
        # 添加总结
        report.append("## 📊 总结")
        report.append(f"总通过: {total_passed}")
        report.append(f"总失败: {total_failed}")
        report.append(f"总用时: {total_duration:.2f}s")
        
        if total_failed == 0:
            report.append("🎉 所有测试通过！")
        else:
            report.append(f"⚠️ {total_failed} 个测试失败，需要检查")
        
        return "\n".join(report)
    
    def save_report(self, report: str, filename: str = "test_report.txt"):
        """保存测试报告"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"📄 报告已保存到: {filename}")
    
    def _extract_duration(self, output: str) -> str:
        """从pytest输出中提取运行时间"""
        import re
        match = re.search(r'in (\d+\.\d+)s', output)
        return match.group(1) + "s" if match else "N/A"
    
    def _extract_test_stats(self, output: str) -> Dict[str, int]:
        """从pytest输出中提取测试统计信息"""
        import re
        
        # 匹配 "X passed, Y failed" 格式
        match = re.search(r'(\d+) passed(?:, (\d+) failed)?', output)
        if match:
            passed = int(match.group(1))
            failed = int(match.group(2)) if match.group(2) else 0
            return {'passed': passed, 'failed': failed}
        
        return {}


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="监听模块测试运行器")
    parser.add_argument("--test-type", choices=[
        "unit", "integration", "performance", "coverage", 
        "smoke", "all"
    ], default="all", help="测试类型")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--include-slow", action="store_true", help="包含慢速测试")
    parser.add_argument("--pattern", "-k", help="运行匹配模式的测试")
    parser.add_argument("--report", "-r", help="报告文件名", default="test_report.txt")
    parser.add_argument("--test-dir", help="测试目录路径")
    
    args = parser.parse_args()
    
    # 创建测试运行器
    test_dir = Path(args.test_dir) if args.test_dir else None
    runner = TestRunner(test_dir)
    
    results = {}
    
    try:
        if args.pattern:
            # 运行特定模式的测试
            results['specific_tests'] = runner.run_specific_tests(args.pattern, args.verbose)
        elif args.test_type == "unit":
            results['unit_tests'] = runner.run_unit_tests(args.verbose)
        elif args.test_type == "integration":
            results['integration_tests'] = runner.run_integration_tests(args.verbose)
        elif args.test_type == "performance":
            results['performance_tests'] = runner.run_performance_tests(args.verbose)
        elif args.test_type == "coverage":
            results['coverage_analysis'] = runner.run_coverage_analysis()
        elif args.test_type == "smoke":
            results['smoke_tests'] = runner.run_smoke_tests()
        elif args.test_type == "all":
            # 运行完整测试套件
            print("🏁 开始完整测试流程...")
            
            # 1. 冒烟测试
            results['smoke_tests'] = runner.run_smoke_tests()
            if results['smoke_tests']['returncode'] != 0:
                print("❌ 冒烟测试失败，终止后续测试")
                return 1
            
            # 2. 单元测试
            results['unit_tests'] = runner.run_unit_tests(args.verbose)
            
            # 3. 集成测试
            results['integration_tests'] = runner.run_integration_tests(args.verbose)
            
            # 4. 性能测试
            results['performance_tests'] = runner.run_performance_tests(args.verbose)
            
            # 5. 覆盖率分析
            results['coverage_analysis'] = runner.run_coverage_analysis()
        
        # 生成并保存报告
        report = runner.generate_report(results)
        print("\n" + report)
        runner.save_report(report, args.report)
        
        # 检查是否有失败的测试
        has_failures = any(result['returncode'] != 0 for result in results.values())
        
        if has_failures:
            print("\n❌ 部分测试失败")
            return 1
        else:
            print("\n✅ 所有测试通过")
            return 0
            
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        return 130
    except Exception as e:
        print(f"\n💥 运行测试时出错: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 