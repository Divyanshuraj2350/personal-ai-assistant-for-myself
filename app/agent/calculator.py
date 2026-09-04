import ast
import operator
import math


OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculate(expression):
    try:
        tree = ast.parse(expression, mode="eval")
        return evaluate(tree.body)
    except Exception:
        return None


def evaluate(node):

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.BinOp):
        operation = OPERATORS.get(type(node.op))

        if operation is None:
            raise ValueError("Unsupported operator")

        left = evaluate(node.left)
        right = evaluate(node.right)

        return operation(left, right)

    if isinstance(node, ast.UnaryOp):
        operation = OPERATORS.get(type(node.op))

        if operation is None:
            raise ValueError("Unsupported operator")

        return operation(evaluate(node.operand))

    raise ValueError("Invalid expression")