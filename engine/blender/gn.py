"""A small builder for Geometry Nodes trees, so realism blocks read as the maths in engine/physics, not
as node plumbing. Runs inside Blender only (import it inside build(), never from host code)."""
import bpy


def _sock(v):
    return hasattr(v, "is_output")


class Tree:
    """A node group. Default: a deformer (Geometry in, Geometry out). Pass inputs/outputs for a function
    group, e.g. inputs=(("Position", "NodeSocketVector"),), outputs=(("Wind", "NodeSocketVector"),)."""

    def __init__(self, name, inputs=(("Geometry", "NodeSocketGeometry"),),
                 outputs=(("Geometry", "NodeSocketGeometry"),)):
        self.ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        for n, t in inputs:
            self.ng.interface.new_socket(n, in_out="INPUT", socket_type=t)
        for n, t in outputs:
            self.ng.interface.new_socket(n, in_out="OUTPUT", socket_type=t)
        self._in = self.ng.nodes.new("NodeGroupInput")
        self._out = self.ng.nodes.new("NodeGroupOutput")
        self.geometry = self._in.outputs.get("Geometry")

    def input(self, name):
        return self._in.outputs[name]

    def node(self, idname, **props):
        n = self.ng.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def feed(self, sock, v):
        if _sock(v):
            self.ng.links.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0, c=0.0):
        n = self.node("ShaderNodeMath", operation=op)
        for s, v in zip(n.inputs, (a, b, c)):
            self.feed(s, v)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        if scale is not None:
            self.feed(n.inputs["Scale"], scale)
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Vector"]

    def vec(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        for s, v in zip(n.inputs, (x, y, z)):
            self.feed(s, v)
        return n.outputs[0]

    def xyz(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self.feed(n.inputs[0], v)
        return n.outputs["X"], n.outputs["Y"], n.outputs["Z"]

    def position(self):
        return self.node("GeometryNodeInputPosition").outputs[0]

    def time(self):
        return self.node("GeometryNodeInputSceneTime").outputs["Seconds"]

    def attr(self, name, data_type="FLOAT"):
        n = self.node("GeometryNodeInputNamedAttribute", data_type=data_type)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    def equals(self, a, b):
        """Float compare with epsilon 0.5: reads INT tag attributes (wheel index + 1) exactly."""
        n = self.node("FunctionNodeCompare", data_type="FLOAT", operation="EQUAL")
        self.feed(n.inputs[0], a)
        self.feed(n.inputs[1], b)
        n.inputs["Epsilon"].default_value = 0.5
        return n.outputs[0]

    def self_object(self):
        return self.node("GeometryNodeSelfObject").outputs[0]

    def object_transform(self, obj, space="ORIGINAL"):
        n = self.node("GeometryNodeObjectInfo", transform_space=space)
        self.feed(n.inputs["Object"], obj)
        return n.outputs["Transform"]

    def object_location(self, obj):
        n = self.node("GeometryNodeObjectInfo", transform_space="ORIGINAL")
        self.feed(n.inputs["Object"], obj)
        return n.outputs["Location"]

    def invert(self, m):
        n = self.node("FunctionNodeInvertMatrix")
        self.feed(n.inputs[0], m)
        return n.outputs["Matrix"]

    def matmul(self, a, b):
        n = self.node("FunctionNodeMatrixMultiply")
        self.feed(n.inputs[0], a)
        self.feed(n.inputs[1], b)
        return n.outputs[0]

    def point(self, v, m):
        n = self.node("FunctionNodeTransformPoint")
        self.feed(n.inputs["Vector"], v)
        self.feed(n.inputs["Transform"], m)
        return n.outputs[0]

    def translation(self, m):
        n = self.node("FunctionNodeSeparateTransform")
        self.feed(n.inputs[0], m)
        return n.outputs["Translation"]

    def rotate(self, v, axis, angle):
        r = self.node("FunctionNodeAxisAngleToRotation")
        self.feed(r.inputs["Axis"], axis)
        self.feed(r.inputs["Angle"], angle)
        n = self.node("FunctionNodeRotateVector")
        self.feed(n.inputs["Vector"], v)
        self.feed(n.inputs["Rotation"], r.outputs[0])
        return n.outputs[0]

    def switch_vec(self, cond, if_false, if_true):
        n = self.node("GeometryNodeSwitch", input_type="VECTOR")
        self.feed(n.inputs["Switch"], cond)
        self.feed(n.inputs["False"], if_false)
        self.feed(n.inputs["True"], if_true)
        return n.outputs[0]

    def smoothstep(self, e0, e1, x):
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        n.clamp = True
        self.feed(n.inputs["Value"], x)
        self.feed(n.inputs["From Min"], e0)
        self.feed(n.inputs["From Max"], e1)
        n.inputs["To Min"].default_value, n.inputs["To Max"].default_value = 0.0, 1.0
        return n.outputs["Result"]

    def noise(self, v, scale=1.0):
        n = self.node("ShaderNodeTexNoise")
        self.feed(n.inputs["Vector"], v)
        n.inputs["Scale"].default_value = scale
        return n.outputs["Factor"], n.outputs["Color"]

    def group(self, ng, **inputs):
        n = self.node("GeometryNodeGroup")
        n.node_tree = ng
        for k, v in inputs.items():
            self.feed(n.inputs[k], v)
        return n

    def store(self, name, value, data_type="FLOAT", domain="POINT"):
        n = self.node("GeometryNodeStoreNamedAttribute", data_type=data_type, domain=domain)
        self.feed(n.inputs["Geometry"], self.geometry)
        n.inputs["Name"].default_value = name
        self.feed(n.inputs["Value"], value)
        self.geometry = n.outputs["Geometry"]

    def set_position(self, pos, selection=None):
        n = self.node("GeometryNodeSetPosition")
        self.feed(n.inputs["Geometry"], self.geometry)
        if selection is not None:
            self.feed(n.inputs["Selection"], selection)
        self.feed(n.inputs["Position"], pos)
        self.geometry = n.outputs["Geometry"]

    def output(self, name, sock):
        self.ng.links.new(sock, self._out.inputs[name])

    def finish(self):
        if self.geometry is not None and "Geometry" in self._out.inputs:
            self.ng.links.new(self.geometry, self._out.inputs["Geometry"])
        return self.ng


def add_modifier(obj, ng, name):
    mod = obj.modifiers.new(name, "NODES")
    mod.node_group = ng
    return mod


def placed(t, offset):
    """(P, back): this vertex in placed space, and a function mapping a placed-space point back to the
    object's local space. rel = inverse(M_self) @ M_offset maps placed -> local."""
    rel = t.matmul(t.invert(t.object_transform(t.self_object())), t.object_transform(offset))
    return t.point(t.position(), t.invert(rel)), (lambda v: t.point(v, rel))


def ground_in_placed(t, offset, world_z):
    """Placed-space height of the world plane z = world_z under the realism offset (which translates and
    scales but never tilts)."""
    m = t.object_transform(offset)
    x, y, _ = t.xyz(t.translation(m))
    return t.xyz(t.point(t.vec(x, y, world_z), t.invert(m)))[2]
