"""Verify chassis.py has no TF2 dependencies after removal."""
import ast
import os

CHASSIS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dicemaster_central", "dicemaster_central", "hw", "chassis.py",
)

def _get_imports(filepath):
    """Extract all import names from a Python file using AST."""
    with open(filepath) as f:
        tree = ast.parse(f.read())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports

def test_no_tf2_imports():
    imports = _get_imports(CHASSIS_PATH)
    tf2_imports = {i for i in imports if "tf2" in i}
    assert not tf2_imports, f"TF2 imports still present: {tf2_imports}"

def test_no_transform_stamped_import():
    imports = _get_imports(CHASSIS_PATH)
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "TransformStamped" not in source, "TransformStamped still referenced"

def test_no_pose_import():
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "from geometry_msgs.msg import Pose" not in source

def test_no_timer_callback_method():
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "def timer_callback" not in source
    assert "_publish_dynamic_transforms" not in source

def test_no_publish_rate_parameter():
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "'publish_rate'" not in source

def test_single_threaded_executor():
    with open(CHASSIS_PATH) as f:
        source = f.read()
    assert "SingleThreadedExecutor" in source
    assert "MultiThreadedExecutor" not in source
