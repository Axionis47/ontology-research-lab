import Std

/-!
Pure, finite canonical OaK plans. Primitive and expression interpretations are
parameters, so the theorem applies to every deterministic interpretation and
every shared immutable graph/input. This does not establish Python lowering,
source completeness, extraction accuracy, or task correctness.
-/
namespace OakPreservation

structure Instruction where
  operator : String
  arguments : String
  deriving DecidableEq, Repr

structure Plan where
  inputs : String
  output : String
  steps : List Instruction
  result : String
  deriving DecidableEq, Repr

structure Observation (Value Error : Type) where
  outcome : Except Error Value
  calls : List Instruction
  deriving Repr

def runSteps {Value Error Graph Input : Type}
    (invoke : Instruction → Graph → Input → List Value → Except Error Value)
    (finish : String → Graph → Input → List Value → Except Error Value)
    (graph : Graph) (input : Input) (result : String) :
    List Instruction → List Value → List Instruction → Observation Value Error
  | [], values, calls => ⟨finish result graph input values, calls⟩
  | instruction :: rest, values, calls =>
    match invoke instruction graph input values with
    | .error error => ⟨.error error, calls ++ [instruction]⟩
    | .ok value => runSteps invoke finish graph input result rest
        (values ++ [value]) (calls ++ [instruction])

def evaluate {Value Error Graph Input : Type}
    (validate : String → Input → Except Error Unit)
    (invoke : Instruction → Graph → Input → List Value → Except Error Value)
    (finish : String → String → Graph → Input → List Value → Except Error Value)
    (plan : Plan) (graph : Graph) (input : Input) : Observation Value Error :=
  match validate plan.inputs input with
  | .error error => ⟨.error error, []⟩
  | .ok _ => runSteps invoke (finish plan.output) graph input plan.result plan.steps [] []

theorem identity {Value Error Graph Input : Type}
    (validate : String → Input → Except Error Unit)
    (invoke : Instruction → Graph → Input → List Value → Except Error Value)
    (finish : String → String → Graph → Input → List Value → Except Error Value)
    (plan : Plan) (graph : Graph) (input : Input) :
    evaluate validate invoke finish plan graph input =
      evaluate validate invoke finish plan graph input := rfl

theorem canonical_preservation {Value Error Graph Input : Type}
    (validate : String → Input → Except Error Unit)
    (invoke : Instruction → Graph → Input → List Value → Except Error Value)
    (finish : String → String → Graph → Input → List Value → Except Error Value)
    (before after : Plan) (same : before = after) (graph : Graph) (input : Input) :
    evaluate validate invoke finish before graph input =
      evaluate validate invoke finish after graph input := by
  cases same
  rfl

theorem transitive_preservation {Value Error Graph Input : Type}
    (validate : String → Input → Except Error Unit)
    (invoke : Instruction → Graph → Input → List Value → Except Error Value)
    (finish : String → String → Graph → Input → List Value → Except Error Value)
    (first middle last : Plan) (left : first = middle) (right : middle = last)
    (graph : Graph) (input : Input) :
    evaluate validate invoke finish first graph input =
      evaluate validate invoke finish last graph input := by
  exact canonical_preservation validate invoke finish first last (left.trans right) graph input

/- Exact macro abstraction is represented by partitioning an unchanged eager
instruction sequence. Expansion must not duplicate, omit, or reorder calls. -/
def expand (blocks : List (List Instruction)) : List Instruction := blocks.flatten

private theorem append_nil_p {A : Type} (items : List A) : items ++ [] = items := by
  induction items with
  | nil => rfl
  | cons item rest ih => exact congrArg (List.cons item) ih

private theorem append_assoc_p {A : Type} (a b c : List A) :
    (a ++ b) ++ c = a ++ (b ++ c) := by
  induction a with
  | nil => rfl
  | cons item rest ih => exact congrArg (List.cons item) ih

theorem exact_abstraction (leading body trailing : List Instruction) :
    expand [leading, body, trailing] = leading ++ body ++ trailing := by
  change leading ++ (body ++ (trailing ++ [])) = (leading ++ body) ++ trailing
  exact (congrArg (fun rest => leading ++ (body ++ rest))
    (append_nil_p trailing)).trans (append_assoc_p leading body trailing).symm

theorem sequence_congruence (a b c d : List Instruction)
    (left : a = b) (right : c = d) : a ++ c = b ++ d := by
  cases left
  cases right
  rfl

#print axioms canonical_preservation
#print axioms transitive_preservation
#print axioms exact_abstraction
#print axioms sequence_congruence

end OakPreservation
