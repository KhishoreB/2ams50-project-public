"""
This file contains functions to plot LinTim networks and solutions using libraries in Python.
Mandl/Athens line-concept visualizations (stops have coordinates, so this is cheap) + later the Pareto frontier plot that S4's sweep will fill in.
"""

from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
from src.parser import PTNInstance, Line
from src.validator import ValidationReport

def plot_line_plan(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], title: str = "Line Plan Visualization") -> None:
    """
    Plots the line plan on a 2D map using matplotlib.
    Stops are represented as points, and lines are represented as colored segments.
    """
    plt.figure(figsize=(12, 8))
    plt.title(title)
    
    # Plot stops
    for stop_id, stop in ptn.stops.items():
        plt.scatter(stop.x, stop.y, color='black', s=10)
        plt.text(stop.x, stop.y, str(stop_id), fontsize=8, ha='right', va='bottom')

    # Prepare line segments for plotting
    line_segments = []
    line_colors = []
    
    for l_id, frequency in frequencies.items():
        if frequency > 0:
            line = pool[l_id]
            coords = [(ptn.stops[stop_id].x, ptn.stops[stop_id].y) for stop_id in line.nodes]
            line_segments.append(coords)
            line_colors.append(frequency)  # Use frequency to determine color intensity

    # Create a LineCollection from the segments
    lc = LineCollection(line_segments, cmap='viridis', linewidths=2)
    lc.set_array(line_colors)
    
    plt.gca().add_collection(lc)
    plt.colorbar(lc, label='Line Frequency')
    
    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.axis('equal')
    plt.grid(True)
    plt.show()

def plot_pareto_frontier(costs: List[float], direct_travelers: List[float], title: str = "Pareto Frontier") -> None:
    """
    Plots the Pareto frontier given costs and direct travelers.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(costs, direct_travelers, color='blue', label='Solutions')
    
    # Highlight the Pareto frontier
    pareto_front = sorted(zip(costs, direct_travelers), key=lambda x: (x[0], -x[1]))
    pareto_costs, pareto_travelers = zip(*pareto_front)
    
    plt.plot(pareto_costs, pareto_travelers, color='red', label='Pareto Frontier', linewidth=2)
    
    plt.title(title)
    plt.xlabel('Total Cost')
    plt.ylabel('Direct Travelers')
    plt.legend()
    plt.grid(True)
    plt.show()

def plot_line_plan_with_violations(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], min_violations: List[Tuple[int, int, int]], max_violations: List[Tuple[int, int, int]], title: str = "Line Plan with Violations") -> None:
    """
    Plots the line plan and highlights edges with frequency violations.
    """
    plt.figure(figsize=(12, 8))
    plt.title(title)
    
    # Plot stops
    for stop_id, stop in ptn.stops.items():
        plt.scatter(stop.x, stop.y, color='black', s=10)
        plt.text(stop.x, stop.y, str(stop_id), fontsize=8, ha='right', va='bottom')

    # Prepare line segments for plotting
    line_segments = []
    line_colors = []
    
    for l_id, frequency in frequencies.items():
        if frequency > 0:
            line = pool[l_id]
            coords = [(ptn.stops[stop_id].x, ptn.stops[stop_id].y) for stop_id in line.nodes]
            line_segments.append(coords)
            line_colors.append(frequency)  # Use frequency to determine color intensity

    # Create a LineCollection from the segments
    lc = LineCollection(line_segments, cmap='viridis', linewidths=2)
    lc.set_array(line_colors)
    
    plt.gca().add_collection(lc)
    
    # Highlight violations
    for e_id, act_f, min_f in min_violations:
        edge = ptn.edges[e_id]
        x_coords = [ptn.stops[edge.u].x, ptn.stops[edge.v].x]
        y_coords = [ptn.stops[edge.u].y, ptn.stops[edge.v].y]
        plt.plot(x_coords, y_coords, color='red', linewidth=3, label='Under-served Edge' if e_id == min_violations[0][0] else "")
    
    for e_id, act_f, max_f in max_violations:
        edge = ptn.edges[e_id]
        x_coords = [ptn.stops[edge.u].x, ptn.stops[edge.v].x]
        y_coords = [ptn.stops[edge.u].y, ptn.stops[edge.v].y]
        plt.plot(x_coords, y_coords, color='orange', linewidth=3, label='Over-capacity Edge' if e_id == max_violations[0][0] else "")
    
    plt.colorbar(lc, label='Line Frequency')
    
    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.axis('equal')
    plt.grid(True)
    plt.legend()
    plt.show()

def plot_line_plan_summary(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], validation_report: ValidationReport) -> None:
    """
    Plots the line plan along with a summary of the validation report.
    """
    plot_line_plan_with_violations(ptn, pool, frequencies, validation_report.min_frequency_violations, validation_report.max_frequency_violations, title="Line Plan Summary")
    
    print(validation_report.summary())

def plot_pareto_frontier_with_solutions(costs: List[float], direct_travelers: List[float], solutions: List[Dict[int, int]], title: str = "Pareto Frontier with Solutions") -> None:
    """
    Plots the Pareto frontier and annotates specific solutions on the plot.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(costs, direct_travelers, color='blue', label='Solutions')
    
    # Highlight the Pareto frontier
    pareto_front = sorted(zip(costs, direct_travelers), key=lambda x: (x[0], -x[1]))
    pareto_costs, pareto_travelers = zip(*pareto_front)
    
    plt.plot(pareto_costs, pareto_travelers, color='red', label='Pareto Frontier', linewidth=2)
    
    # Annotate specific solutions
    for i, (cost, travelers) in enumerate(zip(costs, direct_travelers)):
        plt.annotate(f'Sol {i+1}', (cost, travelers), textcoords="offset points", xytext=(0,10), ha='center')
    
    plt.title(title)
    plt.xlabel('Total Cost')
    plt.ylabel('Direct Travelers')
    plt.legend()
    plt.grid(True)
    plt.show()

def plot_line_plan_with_costs(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], costs: Dict[int, float], title: str = "Line Plan with Costs") -> None:
    """
    Plots the line plan and annotates each line with its associated cost.
    """
    plt.figure(figsize=(12, 8))
    plt.title(title)
    
    # Plot stops
    for stop_id, stop in ptn.stops.items():
        plt.scatter(stop.x, stop.y, color='black', s=10)
        plt.text(stop.x, stop.y, str(stop_id), fontsize=8, ha='right', va='bottom')

    # Prepare line segments for plotting
    line_segments = []
    line_colors = []
    
    for l_id, frequency in frequencies.items():
        if frequency > 0:
            line = pool[l_id]
            coords = [(ptn.stops[stop_id].x, ptn.stops[stop_id].y) for stop_id in line.nodes]
            line_segments.append(coords)
            line_colors.append(frequency)  # Use frequency to determine color intensity

            # Annotate with cost
            mid_x = sum(ptn.stops[stop_id].x for stop_id in line.nodes) / len(line.nodes)
            mid_y = sum(ptn.stops[stop_id].y for stop_id in line.nodes) / len(line.nodes)
            plt.text(mid_x, mid_y, f'Cost: {costs[l_id]:.2f}', fontsize=8, ha='center', va='center', color='blue')

    # Create a LineCollection from the segments
    lc = LineCollection(line_segments, cmap='viridis', linewidths=2)
    lc.set_array(line_colors)
    
    plt.gca().add_collection(lc)
    plt.colorbar(lc, label='Line Frequency')
    
    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.axis('equal')
    plt.grid(True)
    plt.show()

def plot_line_plan_with_frequencies(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], title: str = "Line Plan with Frequencies") -> None:
    """
    Plots the line plan and annotates each line with its frequency.
    """
    plt.figure(figsize=(12, 8))
    plt.title(title)
    
    # Plot stops
    for stop_id, stop in ptn.stops.items():
        plt.scatter(stop.x, stop.y, color='black', s=10)
        plt.text(stop.x, stop.y, str(stop_id), fontsize=8, ha='right', va='bottom')

    # Prepare line segments for plotting
    line_segments = []
    line_colors = []
    
    for l_id, frequency in frequencies.items():
        if frequency > 0:
            line = pool[l_id]
            coords = [(ptn.stops[stop_id].x, ptn.stops[stop_id].y) for stop_id in line.nodes]
            line_segments.append(coords)
            line_colors.append(frequency)  # Use frequency to determine color intensity

            # Annotate with frequency
            mid_x = sum(ptn.stops[stop_id].x for stop_id in line.nodes) / len(line.nodes)
            mid_y = sum(ptn.stops[stop_id].y for stop_id in line.nodes) / len(line.nodes)
            plt.text(mid_x, mid_y, f'Freq: {frequency}', fontsize=8, ha='center', va='center', color='green')

    # Create a LineCollection from the segments
    lc = LineCollection(line_segments, cmap='viridis', linewidths=2)
    lc.set_array(line_colors)
    
    plt.gca().add_collection(lc)
    plt.colorbar(lc, label='Line Frequency')
    
    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.axis('equal')
    plt.grid(True)
    plt.show()

def plot_line_plan_with_summary(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], validation_report: ValidationReport, title: str = "Line Plan with Summary") -> None:
    """
    Plots the line plan and displays a summary of the validation report.
    """
    plot_line_plan_with_violations(ptn, pool, frequencies, validation_report.min_frequency_violations, validation_report.max_frequency_violations, title=title)
    
    print(validation_report.summary())

def plot_pareto_frontier_with_summary(costs: List[float], direct_travelers: List[float], solutions: List[Dict[int, int]], title: str = "Pareto Frontier with Summary") -> None:
    """
    Plots the Pareto frontier and annotates specific solutions on the plot, along with a summary.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(costs, direct_travelers, color='blue', label='Solutions')
    
    # Highlight the Pareto frontier
    pareto_front = sorted(zip(costs, direct_travelers), key=lambda x: (x[0], -x[1]))
    pareto_costs, pareto_travelers = zip(*pareto_front)
    
    plt.plot(pareto_costs, pareto_travelers, color='red', label='Pareto Frontier', linewidth=2)
    
    # Annotate specific solutions
    for i, (cost, travelers) in enumerate(zip(costs, direct_travelers)):
        plt.annotate(f'Sol {i+1}', (cost, travelers), textcoords="offset points", xytext=(0,10), ha='center')
    
    plt.title(title)
    plt.xlabel('Total Cost')
    plt.ylabel('Direct Travelers')
    plt.legend()
    plt.grid(True)
    plt.show()
    
    # Print summary of solutions
    for i, (cost, travelers) in enumerate(zip(costs, direct_travelers)):
        print(f"Solution {i+1}: Total Cost = {cost:.2f}, Direct Travelers = {travelers:.1f}")

def plot_line_plan_with_costs_and_frequencies(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], costs: Dict[int, float], title: str = "Line Plan with Costs and Frequencies") -> None:
    """
    Plots the line plan and annotates each line with its associated cost and frequency.
    """
    plt.figure(figsize=(12, 8))
    plt.title(title)
    
    # Plot stops
    for stop_id, stop in ptn.stops.items():
        plt.scatter(stop.x, stop.y, color='black', s=10)
        plt.text(stop.x, stop.y, str(stop_id), fontsize=8, ha='right', va='bottom')

    # Prepare line segments for plotting
    line_segments = []
    line_colors = []
    
    for l_id, frequency in frequencies.items():
        if frequency > 0:
            line = pool[l_id]
            coords = [(ptn.stops[stop_id].x, ptn.stops[stop_id].y) for stop_id in line.nodes]
            line_segments.append(coords)
            line_colors.append(frequency)  # Use frequency to determine color intensity

            # Annotate with cost and frequency
            mid_x = sum(ptn.stops[stop_id].x for stop_id in line.nodes) / len(line.nodes)
            mid_y = sum(ptn.stops[stop_id].y for stop_id in line.nodes) / len(line.nodes)
            plt.text(mid_x, mid_y, f'Cost: {costs[l_id]:.2f}\nFreq: {frequency}', fontsize=8, ha='center', va='center', color='blue')

    # Create a LineCollection from the segments
    lc = LineCollection(line_segments, cmap='viridis', linewidths=2)
    lc.set_array(line_colors)
    
    plt.gca().add_collection(lc)
    plt.colorbar(lc, label='Line Frequency')
    
    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.axis('equal')
    plt.grid(True)
    plt.show()

def plot_line_plan_with_summary_and_costs(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], validation_report: ValidationReport, costs: Dict[int, float], title: str = "Line Plan with Summary and Costs") -> None:
    """
    Plots the line plan and displays a summary of the validation report along with costs.
    """
    plot_line_plan_with_costs(ptn, pool, frequencies, costs, title=title)
    
    print(validation_report.summary())

def plot_line_plan_with_summary_and_frequencies(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], validation_report: ValidationReport, title: str = "Line Plan with Summary and Frequencies") -> None:
    """
    Plots the line plan and displays a summary of the validation report along with frequencies.
    """
    plot_line_plan_with_frequencies(ptn, pool, frequencies, title=title)
    
    print(validation_report.summary())

def plot_line_plan_with_summary_costs_and_frequencies(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], validation_report: ValidationReport, costs: Dict[int, float], title: str = "Line Plan with Summary, Costs, and Frequencies") -> None:
    """
    Plots the line plan and displays a summary of the validation report along with costs and frequencies.
    """
    plot_line_plan_with_costs_and_frequencies(ptn, pool, frequencies, costs, title=title)
    
    print(validation_report.summary())

def plot_pareto_frontier_with_summary_and_solutions(costs: List[float], direct_travelers: List[float], solutions: List[Dict[int, int]], title: str = "Pareto Frontier with Summary and Solutions") -> None:
    """
    Plots the Pareto frontier and annotates specific solutions on the plot, along with a summary of the solutions.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(costs, direct_travelers, color='blue', label='Solutions')
    
    # Highlight the Pareto frontier
    pareto_front = sorted(zip(costs, direct_travelers), key=lambda x: (x[0], -x[1]))
    pareto_costs, pareto_travelers = zip(*pareto_front)
    
    plt.plot(pareto_costs, pareto_travelers, color='red', label='Pareto Frontier', linewidth=2)
    
    # Annotate specific solutions
    for i, (cost, travelers) in enumerate(zip(costs, direct_travelers)):
        plt.annotate(f'Sol {i+1}', (cost, travelers), textcoords="offset points", xytext=(0,10), ha='center')
    
    plt.title(title)
    plt.xlabel('Total Cost')
    plt.ylabel('Direct Travelers')
    plt.legend()
    plt.grid(True)
    plt.show()
    
    # Print summary of solutions
    for i, (cost, travelers) in enumerate(zip(costs, direct_travelers)):
        print(f"Solution {i+1}: Total Cost = {cost:.2f}, Direct Travelers = {travelers:.1f}")


def plot_pareto_frontier_with_summary_and_solutions_and_violations(costs: List[float], direct_travelers: List[float], solutions: List[Dict[int, int]], validation_reports: List[ValidationReport], title: str = "Pareto Frontier with Summary, Solutions, and Violations") -> None:
    """
    Plots the Pareto frontier and annotates specific solutions on the plot, along with a summary of the solutions and their violations.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(costs, direct_travelers, color='blue', label='Solutions')
    
    # Highlight the Pareto frontier
    pareto_front = sorted(zip(costs, direct_travelers), key=lambda x: (x[0], -x[1]))
    pareto_costs, pareto_travelers = zip(*pareto_front)
    
    plt.plot(pareto_costs, pareto_travelers, color='red', label='Pareto Frontier', linewidth=2)
    
    # Annotate specific solutions
    for i, (cost, travelers) in enumerate(zip(costs, direct_travelers)):
        plt.annotate(f'Sol {i+1}', (cost, travelers), textcoords="offset points", xytext=(0,10), ha='center')
    
    plt.title(title)
    plt.xlabel('Total Cost')
    plt.ylabel('Direct Travelers')
    plt.legend()
    plt.grid(True)
    plt.show()
    
    # Print summary of solutions and their violations
    for i, (cost, travelers) in enumerate(zip(costs, direct_travelers)):
        report = validation_reports[i]
        print(f"Solution {i+1}: Total Cost = {cost:.2f}, Direct Travelers = {travelers:.1f}")
        print(report.summary())

def plot_line_plan_with_summary_costs_frequencies_and_violations(ptn: PTNInstance, pool: Dict[int, Line], frequencies: Dict[int, int], validation_report: ValidationReport, costs: Dict[int, float], title: str = "Line Plan with Summary, Costs, Frequencies, and Violations") -> None:
    """
    Plots the line plan and displays a summary of the validation report along with costs, frequencies, and violations.
    """
    plot_line_plan_with_violations(ptn, pool, frequencies, validation_report.min_frequency_violations, validation_report.max_frequency_violations, title=title)
    
    print(validation_report.summary())


if __name__ == "__main__":
    # Example usage (assuming you have a PTNInstance, pool, frequencies, and validation_report)
    # ptn = ...  # Load or create your PTNInstance
    # pool = ...  # Load or create your line pool
    # frequencies = ...  # Define your line frequencies
    # validation_report = ...  # Generate your validation report

    # plot_line_plan(ptn, pool, frequencies)
    # plot_pareto_frontier(costs, direct_travelers)
    pass
