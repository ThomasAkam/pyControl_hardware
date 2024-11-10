"""This module contains functions for analysing pyControl the data file generated by the autocalibration task and generating 
the calibration results.  These are a linear fit for each poke giving the release duration needed for a given release volume.
The analysis code can save either independent linear fits for each poke or maximum a posteriori (MAP) fits from a single mixed effects 
regression fit to all the data.  Typically the MAP fits will give a more reliable estimate given the meaurement uncertainly from 
the load cell, but it is advised to look at both fits in the plot to check they look sensible.
"""

# %% Imports
import os
import numpy as np
import ast
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

# %% Global variables
AUTOCALIBRATION_DATA_PATH = "autocalibration_data"
AUTOCALIBRATION_RESULTS_PATH = "autocalibration_results"


def get_poke_calibration_parameters(
    data_filename=None,
    plot=True,
    save_mixed_effects=True,
    save_filename="calibration_results.txt",
):
    """Load data from the specified data file, optionally plot the linear fits, save out either the mixed effects or individual
    linear fits to the specified save file. If no data filename is specifed the most recent datafile is used."""
    autocal_df = load_autocalibration_results(data_filename)
    poke2fit_lr_params = get_linear_regression_parameters(autocal_df)
    poke2fit_me_params = get_mixed_effects_regression_parameters(autocal_df)
    if plot:
        plot_poke_calibration_fits(autocal_df, poke2fit_me_params)
    save_path = os.path.join(AUTOCALIBRATION_RESULTS_PATH, save_filename)
    with open(save_path, "w") as f:
        if save_mixed_effects:  # Save mixed effects regression fits.
            f.write(repr(poke2fit_me_params.T.to_dict()))
        else:  # Save standard linear regression fits.
            f.write(repr(poke2fit_lr_params.T.to_dict()))
    return poke2fit_lr_params, poke2fit_me_params


def load_autocalibration_results(data_filename=None):
    """Load a data file and generate datafame with calibration data.  If no data filename is specifed the most recent
    datafile is used."""
    autocal_files = os.listdir(AUTOCALIBRATION_DATA_PATH)
    autocal_files = [f for f in autocal_files if f.endswith(".tsv")]
    autocal_datetimes = [pd.to_datetime(f.split("-", 1)[1].split(".")[0]) for f in autocal_files]
    if data_filename is None:  # Use most recent data file.
        idx = autocal_datetimes.index(max(autocal_datetimes))
        data_filename = autocal_files[idx]
    assert data_filename in autocal_files, f"Specified file {data_filename} not found in {AUTOCALIBRATION_DATA_PATH}"
    print(f"loading_file: {data_filename}")
    autocal_path = os.path.join(AUTOCALIBRATION_DATA_PATH, data_filename)
    autocal_results = pd.read_csv(autocal_path, sep="\t")
    autocal_results = autocal_results[autocal_results.subtype == "print"].content.apply(ast.literal_eval).to_list()
    autocal_df = pd.DataFrame(autocal_results)
    autocal_df.release_weight = autocal_df.release_weight.apply(abs)
    autocal_df["single_release_vol"] = autocal_df.release_weight.div(autocal_df.n_release).mul(1000)  # in uL
    return autocal_df


def plot_poke_calibration_fits(autocal_df, poke2fit_me_params):
    """Plot the calibration datapoints and linear fits for each poke.  Individual linear fits
    to each poke are plotted in blue, the maximum a posteriori estimates for each poke from
    a mixed effects linear regression are plotted in red."""
    g = sns.FacetGrid(autocal_df, col="poke", col_wrap=7)
    g.map_dataframe(sns.regplot, x="single_release_vol", y="release_duration", ci=None)
    g.map_dataframe(plot_mixed_effects_fit, x="single_release_vol", poke2fit_me_params=poke2fit_me_params)
    g.set_titles(col_template="{col_name}")
    plt.show()
    return


def plot_mixed_effects_fit(data, x, color, poke2fit_me_params):
    """Add mixed effects regression fit to plot."""
    poke = data.poke.unique()[0]
    xmin = data.single_release_vol.min()
    xmax = data.single_release_vol.max()
    intercept = poke2fit_me_params.loc[poke, "i"]
    slope = poke2fit_me_params.loc[poke, "s"]
    ymin = intercept + slope * xmin
    ymax = intercept + slope * xmax
    plt.plot([xmin, xmax], [ymin, ymax], color="r")


def get_linear_regression_parameters(autocal_df):
    """Fit an individual linear regression for each poke predicting release duration from release volume for each poke."""
    poke2fit = {}
    for poke in autocal_df.poke.unique():
        poke_df = autocal_df[autocal_df.poke == poke]
        slope, intercept = np.polyfit(x=poke_df.single_release_vol, y=poke_df.release_duration, deg=1)
        poke2fit[poke] = {"s": round(slope, 2), "i": round(intercept, 2)}  # slope [s] is in ms/uL, intercept [i] in ms.
    return pd.DataFrame(poke2fit).T


def get_mixed_effects_regression_parameters(autocal_df):
    """Fit an mixed effects linear regression to all pokes, predicting release duration from release volume, and return
    the maximum a posteriori fits for each poke."""
    md = smf.mixedlm(
        "release_duration ~ single_release_vol",
        autocal_df,
        groups=autocal_df["poke"],
        re_formula="~ single_release_vol",
    )
    mdf = md.fit(method=["lbfgs"])
    poke2fit = {}
    for poke in autocal_df.poke.unique():
        slope = mdf.fe_params.single_release_vol + mdf.random_effects[poke].single_release_vol
        intercept = mdf.fe_params.Intercept + mdf.random_effects[poke].Group
        poke2fit[poke] = {"s": round(slope, 2), "i": round(intercept, 2)}  # slope [s] is in ms/uL, intercept [i] in ms.
    return pd.DataFrame(poke2fit).T


if __name__ == "__main__":
    get_poke_calibration_parameters()
