from app.agent.planner import create_plan
from app.agent.executor import execute_plan
from app.agent.context_builder import (
    build_execution_context,
)


async def test_pipeline(
    message,
):
    print("\n" + "=" * 70)
    print("MESSAGE:")
    print(message)

    # ==================================================
    # PLANNING
    # ==================================================

    plan = create_plan(
        message
    )

    print("\nPLAN:")
    print(plan)

    # ==================================================
    # EXECUTION
    # ==================================================

    execution = await execute_plan(
        plan=plan,
        message=message,
    )

    print("\nEXECUTION:")
    print(execution)

    # ==================================================
    # CONTEXT BUILDING
    # ==================================================

    context = build_execution_context(
        execution
    )

    print("\nFINAL CONTEXT:")
    print(context)


async def main():

    # ==================================================
    # TEST 1 — NORMAL CHAT
    # ==================================================

    await test_pipeline(
        "Hello, how are you?"
    )

    # ==================================================
    # TEST 2 — CALCULATION
    # ==================================================

    await test_pipeline(
        "What is 125 * 4 + 20?"
    )

    # ==================================================
    # TEST 3 — WEB
    # ==================================================

    await test_pipeline(
        "What are the latest developments in artificial intelligence?"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(
        main()
    )