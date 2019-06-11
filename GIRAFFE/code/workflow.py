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
DataFromOpenNeuro = pe.Node(io.S3DataGrabber(infields=["subj_id", "run_num", "field_template"], outfields=["func", "struct"]), name = 'DataFromOpenNeuro')
DataFromOpenNeuro.inputs.bucket = 'openfmri'
DataFromOpenNeuro.inputs.sort_filelist = True
DataFromOpenNeuro.inputs.template = '*'
DataFromOpenNeuro.inputs.anon = True
DataFromOpenNeuro.inputs.bucket_path = 'ds001/'
DataFromOpenNeuro.inputs.local_directory = '/tmp'
DataFromOpenNeuro.inputs.field_template = dict(func='%s/BOLD/task001_%s/bold.nii.gz', struct='%s/anatomy/highres001_brain.nii.gz')
DataFromOpenNeuro.inputs.template_args =  dict(func=[['subj_id', 'run_num']], struct=[['subj_id']])

#Wraps command **slicetimer**
SliceTimer = pe.MapNode(interface = fsl.SliceTimer(), name='SliceTimer', iterfield = ['in_file'])

#Wraps command **mcflirt**
MotionCorrection = pe.MapNode(interface = fsl.MCFLIRT(), name='MotionCorrection', iterfield = ['in_file'])

#Computes the time-course SNR for a time series
TSNR = pe.MapNode(interface = confounds.TSNR(), name='TSNR', iterfield = ['in_file'])
TSNR.inputs.regress_poly = 3

#Wraps command **fslstats**
ComputeLowTsnr = pe.MapNode(interface = fsl.ImageStats(), name='ComputeLowTsnr', iterfield = ['in_file'])
ComputeLowTsnr.inputs.op_string = '-p 98'

#Wraps command **fslmaths**
Threshold = pe.MapNode(interface = fsl.Threshold(), name='Threshold', iterfield = ['thresh', 'in_file'])
Threshold.inputs.args = '-bin'

#Anatomical compcor: for inputs and outputs, see CompCor.
NoiseComponents = pe.MapNode(interface = confounds.ACompCor(), name='NoiseComponents', iterfield = ['realigned_file', 'mask_files'])
NoiseComponents.inputs.num_components = 2

#Wraps command **fsl_regfilt**
RegressionFilter = pe.MapNode(interface = fsl.FilterRegressor(), name='RegressionFilter', iterfield = ['in_file', 'design_file'])
RegressionFilter.inputs.filter_columns = [1, 2]

#Wraps command **fslmaths**
BandpassFilter = pe.MapNode(interface = fsl.TemporalFilter(), name='BandpassFilter', iterfield = ['in_file'])
BandpassFilter.inputs.highpass_sigma = 25

#Wraps the executable command ``bet``.
BrainExtraction = pe.Node(interface = fsl.BET(), name='BrainExtraction')

#Generic datasink module to store structured outputs
io_DataSink = pe.Node(interface = io.DataSink(), name='io_DataSink')
io_DataSink.inputs.base_directory = '/output/'

#Basic interface class generates identity mappings
Parameters = pe.Node(utility.IdentityInterface(fields=["subj_id", "run_num"]), name='Parameters', iterfield = ['subj_id'])
Parameters.inputs.run_num = ['run001', 'run003']
Parameters.iterables = [('subj_id', ['sub001', 'sub002'])]

#Wraps the executable command ``flirt``.
fsl_FLIRT = pe.Node(interface = fsl.FLIRT(), name='fsl_FLIRT')
fsl_FLIRT.inputs.dof = 6

#Create a workflow to connect all those nodes
analysisflow = nipype.Workflow('MyWorkflow')
analysisflow.connect(SliceTimer, "slice_time_corrected_file", MotionCorrection, "in_file")
analysisflow.connect(MotionCorrection, "out_file", TSNR, "in_file")
analysisflow.connect(TSNR, "stddev_file", ComputeLowTsnr, "in_file")
analysisflow.connect(ComputeLowTsnr, "out_stat", Threshold, "thresh")
analysisflow.connect(MotionCorrection, "out_file", NoiseComponents, "realigned_file")
analysisflow.connect(Threshold, "out_file", NoiseComponents, "mask_files")
analysisflow.connect(NoiseComponents, "components_file", RegressionFilter, "design_file")
analysisflow.connect(TSNR, "detrended_file", RegressionFilter, "in_file")
analysisflow.connect(RegressionFilter, "out_file", BandpassFilter, "in_file")
analysisflow.connect(TSNR, "stddev_file", Threshold, "in_file")
analysisflow.connect(DataFromOpenNeuro, "func", SliceTimer, "in_file")
analysisflow.connect(DataFromOpenNeuro, "struct", BrainExtraction, "in_file")
analysisflow.connect(BandpassFilter, "out_file", io_DataSink, "filtered")
analysisflow.connect(BrainExtraction, "out_file", io_DataSink, "skullstripped")
analysisflow.connect(Parameters, "subj_id", DataFromOpenNeuro, "subj_id")
analysisflow.connect(Parameters, "run_num", DataFromOpenNeuro, "run_num")
analysisflow.connect(BrainExtraction, "out_file", fsl_FLIRT, "in_file")
analysisflow.connect(MotionCorrection, "out_file", fsl_FLIRT, "reference")
analysisflow.connect(fsl_FLIRT, "out_file", io_DataSink, "registered")

#Run the workflow
plugin = 'MultiProc' #adjust your desired plugin here
plugin_args = {'n_procs': 1} #adjust to your number of cores
analysisflow.write_graph(graph2use='flat', format='png', simple_form=False)
analysisflow.run(plugin=plugin, plugin_args=plugin_args)
