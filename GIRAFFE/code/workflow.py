#This is a Nipype generator. Warning, here be dragons.
#!/usr/bin/env python

import sys
import nipype
import nipype.pipeline as pe

import nipype.interfaces.io as io
import nipype.interfaces.fsl as fsl
import nipype.algorithms.confounds as confounds
import nipype.interfaces.utility as utility

#Generic datagrabber module that wraps around glob in an
io_S3DataGrabber = pe.Node(io.S3DataGrabber(infields=["subj_id, run_num, field_template"], outfields=["func, struct"]), name = 'io_S3DataGrabber')
io_S3DataGrabber.inputs.bucket = 'openneuro'
io_S3DataGrabber.inputs.sort_filelist = True
io_S3DataGrabber.inputs.template = '*'
io_S3DataGrabber.inputs.anon = True
io_S3DataGrabber.inputs.bucket_path = 'ds000101/ds000101_R2.0.0/uncompressed/'
io_S3DataGrabber.inputs.local_directory = '/tmp'
io_S3DataGrabber.inputs.subj_id = ['sub001', 'sub002']
io_S3DataGrabber.inputs.run_num = ['run001', 'run003']
io_S3DataGrabber.inputs.field_template = dict(func='%s/BOLD/task001_%s/bold.nii.gz',                                     struct='%s/anatomy/highres001_brain.nii.gz')
io_S3DataGrabber.inputs.template_args =  dict(         func=[['subj_id', 'run_num']], struct=[['subj_id']])

#Wraps command **slicetimer**
fsl_SliceTimer = pe.Node(interface = fsl.SliceTimer(), name='fsl_SliceTimer', iterfield = [''])

#Wraps command **mcflirt**
fsl_MCFLIRT = pe.Node(interface = fsl.MCFLIRT(), name='fsl_MCFLIRT', iterfield = [''])

#Computes the time-course SNR for a time series
confounds_TSNR = pe.Node(interface = confounds.TSNR(), name='confounds_TSNR', iterfield = [''])
confounds_TSNR.inputs.regress_poly = 3

#Wraps command **fslstats**
fsl_ImageStats = pe.Node(interface = fsl.ImageStats(), name='fsl_ImageStats', iterfield = [''])
fsl_ImageStats.inputs.op_string = '-p 98'

#Wraps command **fslmaths**
fsl_Threshold = pe.Node(interface = fsl.Threshold(), name='fsl_Threshold', iterfield = [''])
fsl_Threshold.inputs.args = '-bin'

#Anatomical compcor: for inputs and outputs, see CompCor.
confounds_ACompCor = pe.Node(interface = confounds.ACompCor(), name='confounds_ACompCor', iterfield = [''])
confounds_ACompCor.inputs.num_components = 2

#Wraps command **fsl_regfilt**
fsl_FilterRegressor = pe.Node(interface = fsl.FilterRegressor(), name='fsl_FilterRegressor', iterfield = [''])
fsl_FilterRegressor.inputs.filter_columns = [1, 2]

#Wraps command **fslmaths**
fsl_TemporalFilter = pe.Node(interface = fsl.TemporalFilter(), name='fsl_TemporalFilter', iterfield = [''])
fsl_TemporalFilter.inputs.highpass_sigma = 25

#Change the name of a file based on a mapped format string.
utility_Rename = pe.Node(interface = utility.Rename(), name='utility_Rename', iterfield = [''])
utility_Rename.inputs.format_string = "/output/filtered.nii.gz"

#Wraps the executable command ``bet``.
fsl_BET = pe.Node(interface = fsl.BET(), name='fsl_BET', iterfield = [''])

#Change the name of a file based on a mapped format string.
utility_Rename_1 = pe.Node(interface = utility.Rename(), name='utility_Rename_1', iterfield = [''])
utility_Rename_1.inputs.format_string = "/output/skullstripped.nii.gz"

#Create a workflow to connect all those nodes
analysisflow = nipype.Workflow('MyWorkflow')
analysisflow.connect(fsl_SliceTimer, "slice_time_corrected_file", fsl_MCFLIRT, "in_file")
analysisflow.connect(fsl_MCFLIRT, "out_file", confounds_TSNR, "in_file")
analysisflow.connect(confounds_TSNR, "stddev_file", fsl_ImageStats, "in_file")
analysisflow.connect(fsl_ImageStats, "out_stat", fsl_Threshold, "thresh")
analysisflow.connect(fsl_MCFLIRT, "out_file", confounds_ACompCor, "realigned_file")
analysisflow.connect(fsl_Threshold, "out_file", confounds_ACompCor, "mask_files")
analysisflow.connect(confounds_ACompCor, "components_file", fsl_FilterRegressor, "design_file")
analysisflow.connect(confounds_TSNR, "detrended_file", fsl_FilterRegressor, "in_file")
analysisflow.connect(fsl_FilterRegressor, "out_file", fsl_TemporalFilter, "in_file")
analysisflow.connect(confounds_TSNR, "stddev_file", fsl_Threshold, "in_file")
analysisflow.connect(fsl_TemporalFilter, "out_file", utility_Rename, "in_file")
analysisflow.connect(io_S3DataGrabber, "func", fsl_SliceTimer, "in_file")
analysisflow.connect(io_S3DataGrabber, "struct", fsl_BET, "in_file")
analysisflow.connect(fsl_BET, "out_file", utility_Rename_1, "in_file")

#Run the workflow
plugin = 'MultiProc' #adjust your desired plugin here
plugin_args = {'n_procs': 1} #adjust to your number of cores
analysisflow.write_graph(graph2use='flat', format='png', simple_form=False)
analysisflow.run(plugin=plugin, plugin_args=plugin_args)
