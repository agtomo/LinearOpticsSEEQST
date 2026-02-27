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
                           j: int = None,
                           encoding: str = "pol_path") -> List[OpticalElement]:

    elements = []
    if encoding not in ("pol_path", "path_only"):
        raise ValueError("encoding must be 'pol_path' or 'path_only'")

    # ---- Single-qubit rotations ----
    if gate in ("Rx", "Ry"):
        k = i

        if encoding == "pol_path" and k == 1:
            n_paths = 2 ** (N - 1)

            if gate == "Rx":
                # R^1_x = QWP(0) - HWP(pi/8) - QWP(0)
                for p in range(n_paths):
                    elements.extend([
                        OpticalElement("QWP", {"angle": "0"}, f"path_{p}"),
                        OpticalElement("HWP", {"angle": "pi/8"}, f"path_{p}"),
                        OpticalElement("QWP", {"angle": "0"}, f"path_{p}")
                    ])

            elif gate == "Ry":
                # R^1_y = QWP(pi/4) - HWP(3pi/8) - QWP(pi/4)
                for p in range(n_paths):
                    elements.extend([
                        OpticalElement("QWP", {"angle": "pi/4"}, f"path_{p}"),
                        OpticalElement("HWP", {"angle": "3pi/8"}, f"path_{p}"),
                        OpticalElement("QWP", {"angle": "pi/4"}, f"path_{p}")
                    ])

        elif encoding == "path_only":
            # All qubits are path-encoded
            pairs = paired_paths_for_qubit(N + 1, k + 1)

            if gate == "Rx":
                for p0, p1 in pairs:
                    elements.append(
                        OpticalElement("BS", {}, (p0, p1))
                    )

            elif gate == "Ry":
                # R_y on path qubit:
                # PhasePlate(-pi/2) on first path
                # BS with phi = pi/2
                # PhasePlate(+pi/2) on first path
                for p0, p1 in pairs:
                    elements.append(
                        OpticalElement("PhasePlate", {"phi": "-pi/2"}, p0)
                    )
                    elements.append(
                        OpticalElement("BS", {"phi": "pi/2"}, (p0, p1))
                    )
                    elements.append(
                        OpticalElement("PhasePlate", {"phi": "pi/2"}, p0)
                    )

        else:
            pairs = paired_paths_for_qubit(N, k)

            if gate == "Rx":
                for p0, p1 in pairs:
                    elements.append(
                        OpticalElement("BS", {}, (p0, p1))
                    )

            elif gate == "Ry":
                # R_y on path qubit:
                # PhasePlate(-pi/2) on first path
                # BS with phi = pi/2
                # PhasePlate(+pi/2) on first path
                for p0, p1 in pairs:
                    elements.append(
                        OpticalElement("PhasePlate", {"phi": "-pi/2"}, p0)
                    )
                    elements.append(
                        OpticalElement("BS", {"phi": "pi/2"}, (p0, p1))
                    )
                    elements.append(
                        OpticalElement("PhasePlate", {"phi": "pi/2"}, p0)
                    )

    # ---- CNOT gates ----
    elif gate == "CNOT":

        control = i
        target = j

        if encoding == "pol_path":

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

        elif encoding == "path_only":

            # All qubits are path encoded
            n_path = N
            c_idx = control - 1
            t_idx = target - 1

            for bits in all_bitstrings(n_path):
                if bits[c_idx] == 1 and bits[t_idx] == 0:
                    swapped = list(bits)
                    swapped[t_idx] = 1
                    elements.append(
                        OpticalElement("PathSwap", {}, (bits, tuple(swapped)))
                    )

    else:
        raise ValueError("Unknown gate")

    return elements


# =========================================================
# Circuit Class (Composite Gate Support)
# =========================================================

class OpticalCircuit:

    def __init__(self, N, encoding: str = "pol_path"):
        self.N = N
        self.encoding = encoding
        self.elements: List[OpticalElement] = []
        self.stage = 0

    # Add gate sequentially
    def add_gate(self, gate: str, i=None, j=None):
        elems = optical_implementation(
            gate,
            self.N,
            i=i,
            j=j,
            encoding=self.encoding
        )

        for e in elems:
            e.stage = self.stage

        self.elements.extend(elems)
        self.stage += 1

    # Algebraic composition
    def __mul__(self, other):
        if self.N != other.N:
            raise ValueError("Circuits must have same N")

        new = OpticalCircuit(self.N, encoding=self.encoding)

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