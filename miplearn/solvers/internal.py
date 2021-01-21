#  MIPLearn: Extensible Framework for Learning-Enhanced Mixed-Integer Optimization
#  Copyright (C) 2020, UChicago Argonne, LLC. All rights reserved.
#  Released under the modified BSD license. See COPYING.md for more details.

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from miplearn.instance import Instance
from miplearn.types import (
    LPSolveStats,
    IterationCallback,
    LazyCallback,
    MIPSolveStats,
    VarIndex,
)

logger = logging.getLogger(__name__)


class Constraint:
    pass


class InternalSolver(ABC):
    """
    Abstract class representing the MIP solver used internally by LearningSolver.
    """

    @abstractmethod
    def solve_lp(
        self,
        tee: bool = False,
    ) -> LPSolveStats:
        """
        Solves the LP relaxation of the currently loaded instance. After this
        method finishes, the solution can be retrieved by calling `get_solution`.

        This method should not permanently modify the problem. That is, subsequent
        calls to `solve` should solve the original MIP, not the LP relaxation.

        Parameters
        ----------
        tee
            If true, prints the solver log to the screen.
        """
        pass

    @abstractmethod
    def solve(
        self,
        tee: bool = False,
        iteration_cb: IterationCallback = None,
        lazy_cb: LazyCallback = None,
    ) -> MIPSolveStats:
        """
        Solves the currently loaded instance. After this method finishes,
        the best solution found can be retrieved by calling `get_solution`.

        Parameters
        ----------
        iteration_cb:
            By default, InternalSolver makes a single call to the native `solve`
            method and returns the result. If an iteration callback is provided
            instead, InternalSolver enters a loop, where `solve` and `iteration_cb`
            are called alternatively. To stop the loop, `iteration_cb` should return
            False. Any other result causes the solver to loop again.
        lazy_cb:
            This function is called whenever the solver finds a new candidate
            solution and can be used to add lazy constraints to the model. Only the
            following operations within the callback are allowed:
                - Querying the value of a variable
                - Querying if a constraint is satisfied
                - Adding a new constraint to the problem
            Additional operations may be allowed by specific subclasses.
        tee
            If true, prints the solver log to the screen.
        """
        pass

    @abstractmethod
    def get_solution(self) -> Optional[Dict]:
        """
        Returns current solution found by the solver.

        If called after `solve`, returns the best primal solution found during
        the search. If called after `solve_lp`, returns the optimal solution
        to the LP relaxation. If no primal solution is available, return None.

        The solution is a dictionary `sol`, where the optimal value of `var[idx]`
        is given by `sol[var][idx]`.
        """
        pass

    @abstractmethod
    def set_warm_start(self, solution: Dict) -> None:
        """
        Sets the warm start to be used by the solver.

        The solution should be a dictionary following the same format as the
        one produced by `get_solution`. Only one warm start is supported.
        Calling this function when a warm start already exists will
        remove the previous warm start.
        """
        pass

    @abstractmethod
    def set_instance(
        self,
        instance: Instance,
        model: Any = None,
    ) -> None:
        """
        Loads the given instance into the solver.

        Parameters
        ----------
        instance: Instance
            The instance to be loaded.
        model:
            The concrete optimization model corresponding to this instance
            (e.g. JuMP.Model or pyomo.core.ConcreteModel). If not provided,
            it will be generated by calling `instance.to_model()`.
        """
        pass

    @abstractmethod
    def fix(self, solution: Dict) -> None:
        """
        Fixes the values of a subset of decision variables.

        The values should be provided in the dictionary format generated by
        `get_solution`. Missing values in the solution indicate variables
        that should be left free.
        """
        pass

    def set_branching_priorities(self, priorities: Dict) -> None:
        """
        Sets the branching priorities for the given decision variables.

        When the MIP solver needs to decide on which variable to branch, variables
        with higher priority are picked first, given that they are fractional.
        Ties are solved arbitrarily. By default, all variables have priority zero.

        The priorities should be provided in the dictionary format generated by
        `get_solution`. Missing values indicate variables whose priorities
        should not be modified.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_constraint_ids(self) -> List[str]:
        """
        Returns a list of ids which uniquely identify each constraint in the model.
        """
        pass

    @abstractmethod
    def add_constraint(self, cobj: Constraint) -> None:
        """
        Adds a single constraint to the model.
        """
        pass

    @abstractmethod
    def extract_constraint(self, cid: str) -> Constraint:
        """
        Removes a given constraint from the model and returns an object `cobj` which
        can be used to verify if the removed constraint is still satisfied by
        the current solution, using `is_constraint_satisfied(cobj)`, and can potentially
        be re-added to the model using `add_constraint(cobj)`.
        """
        pass

    @abstractmethod
    def is_constraint_satisfied(self, cobj: Constraint) -> bool:
        """
        Returns True if the current solution satisfies the given constraint.
        """
        pass

    @abstractmethod
    def set_constraint_sense(self, cid: str, sense: str) -> None:
        pass

    @abstractmethod
    def get_constraint_sense(self, cid: str) -> str:
        pass

    @abstractmethod
    def set_constraint_rhs(self, cid: str, rhs: float) -> None:
        pass

    @abstractmethod
    def get_value(self, var_name: str, index: VarIndex) -> Optional[float]:
        """
        Returns the value of a given variable in the current solution. If no
        solution is available, returns None.
        """
        pass

    @abstractmethod
    def relax(self) -> None:
        """
        Drops all integrality constraints from the model.
        """
        pass

    @abstractmethod
    def get_inequality_slacks(self) -> Dict[str, float]:
        """
        Returns a dictionary mapping constraint name to the constraint slack
        in the current solution.
        """
        pass

    @abstractmethod
    def is_infeasible(self) -> bool:
        """
        Returns True if the model has been proved to be infeasible.
        Must be called after solve.
        """
        pass

    @abstractmethod
    def get_dual(self, cid: str) -> float:
        """
        If the model is feasible and has been solved to optimality, returns the
        optimal value of the dual variable associated with this constraint. If the
        model is infeasible, returns a portion of the infeasibility certificate
        corresponding to the given constraint.

        Only available for relaxed problems. Must be called after solve.
        """
        pass

    @abstractmethod
    def get_sense(self) -> str:
        """
        Returns the sense of the problem (either "min" or "max").
        """
        pass

    @abstractmethod
    def get_empty_solution(self) -> Dict:
        """
        Returns a dictionary with the same shape as the one produced by
        `get_solution`, but with all values set to None. This method is
        used by the ML components to query what variables are there in
        the model before a solution is available.
        """
        pass
