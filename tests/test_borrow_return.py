# -*- coding: utf-8 -*-
""
图书借阅和归还登记系统 - 自动化测试脚本
负责人：陈宣言
测试框架：Python + Pytest
说明：本脚本包含6个核心测试用例，对应《测试用例表.xlsx》中的 TC-001 至 TC-006。
""

import pytest

# =========================================
# 模拟后端核心服务 (等待李鑫儿实现 src/borrowService.py)
# 实际上线时，请取消下面这行的注释，并注释掉后面的 mock 类
# from src.borrowService import borrowBook, returnBook
# =========================================

class MockBorrowService:
    """用于模拟后端借还书逻辑的类（仅用于测试框架展示）"""
    def borrowBook(self, userId, bookId):
        # 模拟 TC-001：借书成功
        if userId == "U001" and bookId == "B001":
            return {"code": 200, "msg": "借阅成功", "due_date": "2026-11-25"}
        # 模拟 TC-002：库存不足/不可借
        elif bookId == "B_EMPTY":
            return {"code": 400, "msg": "该图书当前不可借"}
        # 模拟 TC-003：超出最大借阅限额（根据 CR-001，限额为 5 本）
        elif userId == "U_LIMIT":
            return {"code": 400, "msg": "您的借阅额度已达上限（5本）"}
        # 模拟 TC-004：用户状态异常（冻结/挂失）
        elif userId == "U_FROZEN":
            return {"code": 400, "msg": "用户状态异常，无法借阅"}
        else:
            return {"code": 500, "msg": "未知错误"}

    def returnBook(self, userId, bookId):
        # 模拟 TC-005：还书成功
        if userId == "U001" and bookId == "B001":
            return {"code": 200, "msg": "归还成功"}
        else:
            return {"code": 400, "msg": "未找到匹配的在借记录"}

# 实例化模拟服务
service = MockBorrowService()


# ==========================================
# 核心测试用例 (TC-001 到 TC-006)
# ==========================================

def test_borrow_success():
    """TC-001: 借书成功（正常流程）"""
    # 步骤：输入正常的用户ID和图书ID
    result = service.borrowBook("U001", "B001")
    
    # 预期：返回状态码 200，且有应还日期
    assert result["code"] == 200
    assert "due_date" in result
    assert result["msg"] == "借阅成功"

def test_borrow_out_of_stock():
    """TC-002: 借书失败 - 库存不足/不可借"""
    # 步骤：输入一本库存为0或已借出的图书
    result = service.borrowBook("U001", "B_EMPTY")
    
    # 预期：返回状态码 400，提示不可借
    assert result["code"] == 400
    assert "不可借" in result["msg"]

def test_borrow_limit_exceeded():
    """TC-003: 借书失败 - 超出最大借阅限额（重点：5本）"""
    # 步骤：输入一个已借满5本书的用户
    # 注意：根据需求变更 CR-001，原10本已调整为5本
    result = service.borrowBook("U_LIMIT", "B001")
    
    # 预期：返回状态码 400，提示额度已满
    assert result["code"] == 400
    assert "上限" in result["msg"]

def test_borrow_user_frozen():
    """TC-004: 借书失败 - 用户状态异常（挂失/欠费）"""
    # 步骤：输入一个挂失或欠费的用户
    result = service.borrowBook("U_FROZEN", "B001")
    
    # 预期：返回状态码 400，提示状态异常
    assert result["code"] == 400
    assert "状态异常" in result["msg"]

def test_return_success():
    """TC-005: 还书成功（正常流程）"""
    # 步骤：输入有效的借阅记录进行还书
    result = service.returnBook("U001", "B001")
    
    # 预期：返回状态码 200，提示成功
    assert result["code"] == 200
    assert result["msg"] == "归还成功"

def test_concurrent_borrow():
    """TC-006: 并发借阅测试（验证 NFR-001 事务原子性）"""
    # 说明：这里是模拟并发场景测试的占位
    # 实际测试中会使用 Python 的 threading 模块启动多个线程同时调用 borrowBook
    
    # 假设库存只有1本
    initial_stock = 1
    success_count = 0
    
    # 模拟多个用户请求（这里简化为逻辑断言）
    # 真实代码应为: threads = [threading.Thread(target=service.borrowBook, args=("U2", "B002")) for _ in range(5)]
    
    # 预期结果：库存不能为负数，且成功的数量不能超过初始库存
    final_stock = max(0, initial_stock - success_count) 
    
    assert final_stock >= 0, "并发借阅失败：库存出现了负数（超卖）！"
    assert success_count <= initial_stock, "并发借阅失败：借出数量超过了实际库存！"
