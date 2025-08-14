import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from nypl_py_utils.functions.log_helper import create_log

logger = create_log('S3')


def create_graph(labels, scores, elapsed, key, **kwargs):
    """
    Create a graph for given labels, scores, and elapsed values

    Parameters
    ----------
    labels : str[]
        Array of labels for the app versions (e.g. ["V1", "V2", etc])
    scores : number[]
        Array of relevance scores from 0 to 1
    elapsed: number[]
        Array of elapsed scores from 0 to 1 (assumed converted to floats from 0-1)
    """
    global red, blue

    # Primary graph:
    path = f'{kwargs["basedir"]}/graphs/{key}.png'
    if not os.path.exists(path) or kwargs.get('rebuild', False):
        logger.info(f"  Creating figure: {path}")

        blue = "blue"
        red = "red"
        orange = "orange"
        if kwargs.get("palette") is not None:
            blue = kwargs["palette"]["blue"]
            red = kwargs["palette"]["red"]
            orange = kwargs["palette"]["orange"]

        x_ticks = [ind + 1 for ind, v in enumerate(scores)]
        fig, ax = plt.subplots(figsize=(5, 1.5), layout="constrained")
        ax.plot(x_ticks, scores, color=blue)
        ax.plot(x_ticks, elapsed, color=red, linestyle="dashed")
        if "counts" in kwargs:
            ax.plot(x_ticks, kwargs["counts"], color=orange, linestyle="dashed")

        handles = [
            mpatches.Patch(color=red, label="Elapsed"),
            mpatches.Patch(color=blue, label="Score"),
        ]
        if "counts" in kwargs:
            handles.append(mpatches.Patch(color=orange, label="Count"))
        ax.legend(handles=handles)

        y_ticks = [0, 0.5, 1]
        ax.set_yticks(y_ticks, [str(y) for y in y_ticks])
        ax.set_xticks(x_ticks, labels)
        fig.savefig(path)
        plt.close(fig)

    # Thumb:
    path = f'{kwargs["basedir"]}/graphs/{key}-thumb.png'
    if not os.path.exists(path) or kwargs.get('rebuild', False):
        logger.info(f"    Creating fig. thumb: {path}")
        thumb_vals = scores[-3:]

        x_ticks = [ind + 1 for ind, v in enumerate(thumb_vals)]
        fig, ax = plt.subplots(figsize=(0.6, 0.4), layout="constrained")
        ax.plot(x_ticks, thumb_vals, color=blue)

        y_ticks = [0, 0.5, 1]
        ax.set_yticks(y_ticks, ["" for y in y_ticks])
        ax.set_xticks(x_ticks, ["" for v in x_ticks])

        fig.savefig(path)
        plt.close(fig)
