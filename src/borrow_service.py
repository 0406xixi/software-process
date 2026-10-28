# -*- coding: utf-8 -*-
"""
图书馆借阅和归还登记系统 —— 核心业务逻辑
开发负责人：李鑫儿

对应需求（见需求池文档）：
    R-001   借书登记：校验后完成借阅，生成借阅记录并扣减库存
    R-002   还书登记：更新归还记录、恢复库存，并判断是否逾期
    R-003   最大借阅限额控制（本版为 10 本，CR-001 变更后调整为 5 本）
    R-004   用户借阅资格校验（冻结/欠费/超限拒绝借书）
    R-005   库存与图书状态校验
    NFR-001 借还事务完整性：借书“记录+库存-1+计数+1”必须原子完成，失败回滚
    NFR-003 并发借还一致性：多用户同时借同一本书时库存不能为负
"""

import threading
import datetime

# ---------------- 配置区 ----------------
MAX_BORROW_LIMIT = 5    # R-003：每人最多可借图书数量（CR-001 变更：由 10 本调整为 5 本）
OVERDUE_FINE_PER_DAY = 1.0  # 逾期罚金：每天 1 元（R-006 可选功能）


class BorrowService:
    """借阅服务：内存版核心业务逻辑，用锁模拟数据库事务机制。"""

    def __init__(self):
        self._lock = threading.Lock()          # NFR-003：保证并发下库存不为负
        self.users = {}    # user_id -> {"name", "status", "borrowed_count"}
        self.books = {}    # book_id -> {"title", "stock"}
        self.records = []  # 借阅记录列表

    # ---------------- 数据初始化（测试/演示用） ----------------
    def add_user(self, user_id, name, status="正常"):
        self.users[user_id] = {"name": name, "status": status, "borrowed_count": 0}

    def add_book(self, book_id, title, stock):
        self.books[book_id] = {"title": title, "stock": stock}

    # ---------------- 核心功能一：借书（R-001） ----------------
    def borrowBook(self, user_id, book_id):
        """
        借书流程：用户状态校验 -> 限额校验 -> 库存校验 -> 扣减库存
                  -> 累加借阅计数 -> 生成借阅记录。
        任一步失败则整体回滚（NFR-001 事务机制模拟）。
        返回 (是否成功, 提示信息)
        """
        with self._lock:  # ===== 事务开始 =====
            user = self.users.get(user_id)
            book = self.books.get(book_id)

            # R-004 用户借阅资格校验
            if user is None:
                return False, "借书失败：用户不存在"
            if user["status"] != "正常":
                return False, f"借书失败：用户当前状态为[{user['status']}]，无借阅资格"

            # R-003 最大借阅限额校验
            if user["borrowed_count"] >= MAX_BORROW_LIMIT:
                return False, f"借书失败：已达到最大借阅限额（{MAX_BORROW_LIMIT} 本）"

            # R-005 库存与图书状态校验
            if book is None:
                return False, "借书失败：图书不存在"
            if book["stock"] <= 0:
                return False, "借书失败：图书库存不足（已被借完）"

            try:
                # 扣减库存 + 累加借阅计数 + 生成记录，三者原子完成
                book["stock"] -= 1
                user["borrowed_count"] += 1
                record = {
                    "user_id": user_id,
                    "book_id": book_id,
                    "borrow_date": datetime.date.today(),
                    "due_date": datetime.date.today() + datetime.timedelta(days=30),
                    "return_date": None,
                    "fine": 0.0,
                }
                self.records.append(record)
                # ===== 事务提交 =====
                return True, (f"借书成功：《{book['title']}》，应还日期 {record['due_date']}，"
                              f"当前已借 {user['borrowed_count']} 本")
            except Exception as e:
                # ===== 事务回滚：失败则恢复库存与计数 =====
                book["stock"] += 1
                user["borrowed_count"] -= 1
                return False, f"借书失败：系统异常已回滚（{e}）"

    # ---------------- 核心功能二：还书（R-002） ----------------
    def returnBook(self, user_id, book_id):
        """
        还书流程：查找未归还的借阅记录 -> 判断是否逾期并计算罚金
                  -> 恢复库存 -> 更新归还记录 -> 借阅计数减一。
        返回 (是否成功, 提示信息)
        """
        with self._lock:
            user = self.users.get(user_id)
            book = self.books.get(book_id)
            if user is None or book is None:
                return False, "还书失败：用户或图书不存在"

            # 找到该用户该书最早一条未归还记录
            record = None
            for r in self.records:
                if r["user_id"] == user_id and r["book_id"] == book_id and r["return_date"] is None:
                    record = r
                    break
            if record is None:
                return False, "还书失败：未找到对应的借阅记录"

            today = datetime.date.today()
            record["return_date"] = today

            # 逾期判断与罚金计算（R-006）
            if today > record["due_date"]:
                overdue_days = (today - record["due_date"]).days
                record["fine"] = overdue_days * OVERDUE_FINE_PER_DAY
                msg = (f"还书成功：《{book['title']}》已逾期 {overdue_days} 天，"
                       f"罚金 {record['fine']:.1f} 元")
            else:
                msg = f"还书成功：《{book['title']}》按时归还，无罚金"

            # 恢复库存 + 计数减一（与记录更新一起完成）
            book["stock"] += 1
            user["borrowed_count"] -= 1
            return True, msg


# ---------------- 演示：模拟一次完整的借还事务 ----------------
if __name__ == "__main__":
    svc = BorrowService()
    svc.add_user("U001", "张三")
    svc.add_user("U002", "李四", status="冻结")   # 冻结用户，用于 R-004 校验演示
    svc.add_book("B001", "软件工程导论", stock=2)

    print("== 演示 1：正常借书 ==")
    print(svc.borrowBook("U001", "B001"))
    print("== 演示 2：冻结用户借书（R-004 拒绝）==")
    print(svc.borrowBook("U002", "B001"))
    print("== 演示 3：库存不足（R-005 拒绝）==")
    svc.borrowBook("U001", "B001")            # 库存 2 -> 0
    print(svc.borrowBook("U001", "B001"))     # 第三次借：库存不足
    print("== 演示 4：还书 ==")
    print(svc.returnBook("U001", "B001"))
