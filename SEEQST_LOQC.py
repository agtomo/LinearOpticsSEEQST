from itertools import product
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any


# =========================================================
# Data structure
# =========================================================

@dataclass
class OpticalElement:
    element: str
    params: Dict[str, Any]
    location: Any
    stage: int = 0


# =========================================================
# Helpers
# =========================================================

def all_bitstrings(n):
    return list(product([0, 1], repeat=n))


def paired_paths_for_qubit(N: int, k: int):
    n_path = N - 1
    k_idx = k - 2

    pairs = []
    for bits in all_bitstrings(n_path):
        if bits[k_idx] == 0:
            other = list(bits)
            other[k_idx] = 1
            pairs.append((bits, tuple(other)))
    return pairs


def paths_with_bit(N: int, k: int, value: int):
    n_path = N - 1
    k_idx = k - 2
    return [bits for bits in all_bitstrings(n_path) if bits[k_idx] == value]


# =========================================================
# Single-gate compiler (your logic preserved)
# =========================================================

def optical_implementation(gate: str,
                           N: int,
                           i: int = None,
                           j: int = None) -> List[OpticalElement]:

    elements = []

    # ---- Single-qubit rotations ----
    if gate in ("Rx", "Ry"):
        k = i

        if k == 1:
            n_paths = 2 ** (N - 1)

            if gate == "Rx":
                for p in range(n_paths):
                    elements.append(
                        OpticalElement("HWP", {"angle": "pi/2"}, f"path_{p}")
                    )

            elif gate == "Ry":
                for p in range(n_paths):
                    elements.extend([
                        OpticalElement("QWP", {"angle": "pi/4"}, f"path_{p}"),
                        OpticalElement("HWP", {"angle": "pi/2"}, f"path_{p}"),
                        OpticalElement("QWP", {"angle": "pi/4"}, f"path_{p}")
                    ])

        else:
            pairs = paired_paths_for_qubit(N, k)

            if gate == "Rx":
                for p0, p1 in pairs:
                    elements.append(
                        OpticalElement("BS", {}, (p0, p1))
                    )

            elif gate == "Ry":
                zero_paths = paths_with_bit(N, k, 0)
                for p in zero_paths:
                    elements.append(
                        OpticalElement("PhasePlate", {}, p)
                    )

                for p0, p1 in pairs:
                    elements.append(
                        OpticalElement("BS", {}, (p0, p1))
                    )

    # ---- CNOT gates ----
    elif gate == "CNOT":

        control = i
        target = j

        # Polarization -> Path
        if control == 1 and target != 1:
            pairs = paired_paths_for_qubit(N, target)
            for p0, p1 in pairs:
                elements.append(
                    OpticalElement("PBS", {}, (p0, p1))
                )

        # Path -> Path
        elif control != 1 and target != 1:
            n_path = N - 1
            c_idx = control - 2
            t_idx = target - 2

            for bits in all_bitstrings(n_path):
                if bits[c_idx] == 1 and bits[t_idx] == 0:
                    swapped = list(bits)
                    swapped[t_idx] = 1
                    elements.append(
                        OpticalElement("PathSwap", {}, (bits, tuple(swapped)))
                    )

        # Path -> Polarization
        elif control != 1 and target == 1:
            one_paths = paths_with_bit(N, control, 1)
            for p in one_paths:
                elements.append(
                    OpticalElement("HWP", {"angle": "pi/2"}, p)
                )

        else:
            raise ValueError("Unsupported CNOT configuration")

    else:
        raise ValueError("Unknown gate")

    return elements


# =========================================================
# Circuit Class (Composite Gate Support)
# =========================================================

class OpticalCircuit:

    def __init__(self, N):
        self.N = N
        self.elements: List[OpticalElement] = []
        self.stage = 0

    # Add gate sequentially
    def add_gate(self, gate: str, i=None, j=None):
        elems = optical_implementation(gate, self.N, i=i, j=j)

        for e in elems:
            e.stage = self.stage

        self.elements.extend(elems)
        self.stage += 1

    # Algebraic composition
    def __mul__(self, other):
        if self.N != other.N:
            raise ValueError("Circuits must have same N")

        new = OpticalCircuit(self.N)

        new.elements = (
            self.elements +
            [OpticalElement(e.element, e.params, e.location, e.stage + self.stage)
             for e in other.elements]
        )

        new.stage = self.stage + other.stage
        return new

    # Pretty print
    def summary(self):
        print("\n===== Optical Circuit =====")
        for e in sorted(self.elements, key=lambda x: x.stage):
            print(f"Stage {e.stage}: {e.element:10} | loc={e.location} | {e.params}")
        print("===========================\n")


# =========================================================
# Example usage
# =========================================================

# if __name__ == "__main__":

#     N = 4

#     # Sequential build
#     circ = OpticalCircuit(N)
#     circ.add_gate("CNOT", i=1, j=3)
#     circ.add_gate("Rx", i=2)

#     circ.summary()

    # # Algebraic composition version
    # c1 = OpticalCircuit(N)
    # c1.add_gate("Rx", i=1)

    # c2 = OpticalCircuit(N)
    # c2.add_gate("CNOT", i=1, j=2)

    # combined = c1 * c2
    # combined.summary()