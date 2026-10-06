import ast
import operator
import re


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


def extract_expression(message):
    """
    Extract a mathematical expression from
    a natural-language user message.
    """

    if not isinstance(message, str):
        return None

    expression = message.strip()

    # Normalize common multiplication symbols.
    expression = expression.replace("×", "*")
    expression = expression.replace("x", "*")

    # Keep only numbers, decimal points,
    # arithmetic operators, parentheses, and spaces.
    matches = re.findall(
        r"[0-9+\-*/%().\s]+",
        expression,
    )

    if not matches:
        return None

    extracted = "".join(
        matches
    ).strip()

    # Remove extra whitespace.
    extracted = re.sub(
        r"\s+",
        " ",
        extracted,
    )

    if not extracted:
        return None

    # Ensure the extracted value contains
    # at least one digit.
    if not re.search(
        r"\d",
        extracted,
    ):
        return None

    return extracted


def calculate(expression):
    """
    Safely calculate a mathematical expression.

    The input may be either a direct expression
    or a natural-language message containing one.
    """

    try:

        extracted_expression = (
            extract_expression(expression)
        )

        if not extracted_expression:
            return None

        tree = ast.parse(
            extracted_expression,
            mode="eval",
        )

        return evaluate(
            tree.body
        )

    except Exception:
        return None


def evaluate(node):

    # Numbers
    if (
        isinstance(node, ast.Constant)
        and isinstance(
            node.value,
            (int, float),
        )
    ):

        return node.value

    # Binary operations
    if isinstance(
        node,
        ast.BinOp,
    ):

        operation = OPERATORS.get(
            type(node.op)
        )

        if operation is None:
            raise ValueError(
                "Unsupported operator"
            )

        left = evaluate(
            node.left
        )

        right = evaluate(
            node.right
        )

        return operation(
            left,
            right,
        )

    # Unary operations
    if isinstance(
        node,
        ast.UnaryOp,
    ):

        operation = OPERATORS.get(
            type(node.op)
        )

        if operation is None:
            raise ValueError(
                "Unsupported operator"
            )

        return operation(
            evaluate(
                node.operand
            )
        )

    raise ValueError(
        "Invalid expression"
    )