
#from cannon.model import CannonModel
#from cannon.spectral_model import draw_spectra, diagnostics, triangle_pixels, overlay_spectra, residuals
#import numpy as np
import pickle
import random
#import csv
#from matplotlib import rc

plt.rc('text', usetex=True)
plt.rc('font', family='serif')

# STEP 1: DATA MUNGING
import glob
allfiles = glob.glob("example_LAMOST/Data_All/*fits")
allfiles = np.char.lstrip(allfiles, 'example_LAMOST/Data_All/')
tr_ID = np.loadtxt("tr_files.txt", dtype=str)
test_ID = np.setdiff1d(allfiles, tr_ID)

from lamost import load_spectra, load_labels
dir_dat = "example_LAMOST/Data_All"
tr_IDs, wl, tr_flux, tr_ivar = load_spectra(dir_dat, tr_ID)
label_file = "reference_labels.csv"
tr_label = load_labels(label_file, tr_ID)
test_IDs, wl, test_flux, test_ivar = load_spectra(dir_dat, test_ID)

good = np.logical_and(tr_label[:,0] > 0, tr_label[:,2]>-5)
tr_IDs = tr_IDs[good]
tr_flux = tr_flux[good]
tr_ivar = tr_ivar[good]
tr_label = tr_label[good]

from TheCannon import dataset
dataset = dataset.Dataset(
        wl, tr_IDs, tr_flux, tr_ivar, tr_label, test_IDs, test_flux, test_ivar)

# set the headers for plotting
dataset.set_label_names(['T_{eff}', '\log g', '[M/H]', '[\\alpha/Fe]'])

# Plot SNR distributions and triangle plot of reference labels
dataset.diagnostics_SNR()
dataset.diagnostics_ref_labels()

# STEP 2: CONTINUUM IDENTIFICATION

# Pseudo-continuum normalization for the training spectra
if glob.glob('pseudo_normed_spec.p'):
    (pseudo_tr_flux, pseudo_tr_ivar) = pickle.load(
            open("pseudo_normed_spec.p", "r"))

else:
    pseudo_tr_flux, pseudo_tr_ivar = dataset.continuum_normalize_training_q(
            q=0.90, delta_lambda=400)
    pickle.dump((pseudo_tr_flux, pseudo_tr_ivar), 
            open("pseudo_normed_spec.p", "w"))

# From the cont norm training spectra, identify continuum pixels
if glob.glob('contmask.p', 'r'):
    contmask = pickle.load(open("contmask.p", "r"))
else:
    # Identify the best 5% of continuum pixels
    # contmask = dataset.make_contmask(norm_tr_fluxes, norm_tr_ivars, frac=0.05)

    # Identify the best 5% of continuum pixels in each of the following
    # pixel regions 
    dataset.ranges = [[0,50], [50,100], [100,400], [400,600], [600,1722], [1863, 1950], [1950, 2500], [2500,3000], [3000, len(dataset.wl)]]
    contmask = dataset.make_contmask(pseudo_tr_flux, pseudo_tr_ivar, frac=0.05)
    pickle.dump(contmask, open("contmask.p", "w"))

dataset.set_continuum(contmask)


# RUN CONTINUUM NORMALIZATION CODE
dataset.ranges = [[0,1723], [1863,len(dataset.wl)]] # split into two wings

if glob.glob('cont.p', 'r'):
    cont = pickle.load(open("cont.p", "r"))
else:
    cont = dataset.fit_continuum(deg=3, ffunc="sinusoid")
    pickle.dump((cont), open("cont.p", "w"))

# I want the cont for bad pixels to be simply the value, not 0
tr_cont, test_cont = cont
tr_cont[tr_cont==0] = dataset.tr_flux[tr_cont==0] 
test_cont[test_cont==0] = dataset.test_flux[test_cont==0]
cont = tr_cont, test_cont


# Check out the median flux overlaid with cont pix 
f_bar = np.zeros(len(dataset.wl))
sigma_f = np.zeros(len(dataset.wl))
for wl in range(0,len(dataset.wl)):
    flux = pseudo_tr_flux[:,wl]
    ivar = _tr_ivar[:,wl]
    f_bar[wl] = np.median(flux[ivar>0])
    sigma_f[wl] = np.sqrt(np.var(flux[ivar>0]))
bad = np.var(pseudo_tr_ivar, axis=0) == 0
f_bar = np.ma.array(f_bar, mask=bad)
sigma_f = np.ma.array(sigma_f, mask=bad)
plot(dataset.wl, f_bar, alpha=0.7)
fill_between(dataset.wl, (f_bar+sigma_f), (f_bar-sigma_f), alpha=0.2)
scatter(dataset.wl[contmask], f_bar[contmask], c='r')
xlim(3800,9100)
ylim(0,1.1)
xlabel("Wavelength (A)")
ylabel("Median Flux")
title("Median Flux Across Training Spectra Overlaid with Cont Pix")
savefig("medflux_contpix.png")

# Residuals between raw flux and fitted continuum
res = (dataset.tr_flux-tr_cont)*np.sqrt(dataset.tr_ivar)
# sort by temperature...
sorted_res = res[np.argsort(dataset.tr_label[:,2])]
im = plt.imshow(res, cmap=plt.cm.bwr_r, interpolation='nearest', 
        vmin = -80, vmax=10, aspect = 'auto', origin = 'lower',
        extent=[0, len(dataset.wl), 0, nstars])
xlabel("Pixel")
ylabel("Training Object")
title("Residuals in Continuum Fit to Raw Spectra")
colorbar()


# Plot the cont fits for 100 random training stars
tr_cont, test_cont = cont
pickstars = np.zeros(100)
nstars = dataset.tr_flux.shape[0]
for jj in range(10):
    pickstars[jj] = random.randrange(0, nstars-1)

for jj in pickstars:
    #bad = np.var(norm_tr_ivars, axis=0) == 0
    bad = norm_tr_ivar[jj,:] == (1/200.)**2 
    flux = np.ma.array(norm_tr_flux[jj,:], mask=bad)
    plot(dataset.wl, flux, alpha=0.7)
    #scatter(dataset.wl[contmask], flux[contmask], c='r')
    #cont = np.ma.array(tr_cont[jj,:], mask=bad)
    #plot(dataset.wl, cont)
    xlim(3800, 9100)
    title("Sample Continuum Fit")
    xlabel("Wavelength (A)")
    ylabel("Raw Flux")
    savefig('contfit_%s.png' %jj)
    plt.close()

norm_tr_flux, norm_tr_ivar, norm_test_flux, norm_test_ivar = \
        dataset.continuum_normalize(cont)


# If you approve...

dataset.tr_flux = norm_tr_flux
dataset.tr_ivar = norm_tr_ivar
dataset.test_flux = norm_test_flux
dataset.test_ivar = norm_test_ivar

# learn the model from the reference_set
from TheCannon import model
model = model.CannonModel(dataset, 2) # 2 = quadratic model
model.fit() # model.train would work equivalently.
pickle.dump(coeffs_all, open("coeffs_all.p", "w"))

# or...
coeffs_all = pickle.load(open("coeffs_all.p", "r"))

# check the model
model.diagnostics()

# infer labels with the new model for the test_set
if glob.glob('test_labels.p'):
    test_label = pickle.load(open('test_labels.p', 'r'))
    dataset.test_label = test_label
else:
    label_errs = model.infer_labels(dataset)

# Make plots
dataset.dataset_postdiagnostics(dataset)

cannon_set = draw_spectra(model.model, dataset)
diagnostics(cannon_set, dataset, model.model)