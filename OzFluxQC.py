import ast
import copy
import datetime
import logging
import matplotlib
matplotlib.use('TkAgg')
import numpy
import time
import Tkinter as tk
import os
import sys

# The Lindsay Trap: check the scripts directory is present
if not os.path.exists("./scripts/"):
    print "OzFluxQC: the scripts directory is missing"
    sys.exit()
# since the scripts directory is there, try importing the modules
sys.path.append('scripts')
import cfg
import qcclim
import qcgf
import qcio
import qcls
import qcplot
import qcts
import qcutils
# now check the logfiles and plots directories are present
if not os.path.exists("./logfiles/"):
    os.makedirs("./logfiles/")
if not os.path.exists("./plots/"):
    os.makedirs("./plots/")

class qcgui(tk.Tk):
    """
        QC Data Main GUI
        Used to access read, save, and data processing (qcls) prodecures

        Columns: Data levels:
            1:  L1 Raw Data (read excel into NetCDF)
            2:  L2 QA/QC (general QA/QC algorithms, site independent)
            3:  L3 Corrections (Flux data corrections, site dependent based on ancillary measurements available and technical issues)
            4:  L4 Gap Filling (Used for fill met data gaps and ingesting SOLO-ANN Gap Filled fluxes from external processes)

        Rows:  function access
            1:  Ingest excel dataset into NetCDF files
            2:  Process data from previous level and generate NetCDF file(s) at current level
            3-6:  Show Timestamp range of dataset and accept date range for graphical plots
            7:  Export excel dataset from NetCDF file
        """
    def __init__(self, parent):
        tk.Tk.__init__(self,parent)
        self.parent = parent
        self.initialise()

    def option_not_implemented(self):
        self.do_progress(text='Option not implemented yet ...')
        log.info(' Option not implemented yet ...')
    
    def initialise(self):
        self.org_frame = tk.Frame(self)
        self.org_frame.grid()
        # things in the first row of the GUI
        L1Label = tk.Label(self.org_frame,text='L1: Raw data')
        L1Label.grid(row=0,column=0,columnspan=1)
        L2Label = tk.Label(self.org_frame,text='L2: QA/QC')
        L2Label.grid(row=0,column=1,columnspan=1)
        L3Label = tk.Label(self.org_frame,text='L3: Process')
        L3Label.grid(row=0,column=2,columnspan=1)
        L4Label = tk.Label(self.org_frame,text='L4: Gap fill')
        L4Label.grid(row=0,column=3,columnspan=1)
        # things in the second row of the GUI
        doL1Button = tk.Button (self.org_frame, text="Read L1 Excel file", command=self.do_xl2ncL1 )
        doL1Button.grid(row=1,column=0,columnspan=1)
        doL2Button = tk.Button (self.org_frame, text="Do L2 QA/QC", command=self.do_l2qc )
        doL2Button.grid(row=1,column=1,columnspan=1)
        doL3Button = tk.Button (self.org_frame, text="Do L3 processing", command=self.do_l3qc )
        doL3Button.grid(row=1,column=2,columnspan=1)
        doL4Button = tk.Button (self.org_frame, text="Do L4 gap filling", command=self.do_l4qc )
        doL4Button.grid(row=1,column=3,columnspan=1)
        # things in the third row of the GUI
        filestartLabel = tk.Label(self.org_frame,text='File start date')
        filestartLabel.grid(row=2,column=1,columnspan=1)
        fileendLabel = tk.Label(self.org_frame,text='File end date')
        fileendLabel.grid(row=2,column=2,columnspan=1)
        # things in the fourth row of the GUI
        self.filestartValue = tk.Label(self.org_frame,text='No file loaded ...')
        self.filestartValue.grid(row=3,column=1,columnspan=1)
        self.fileendValue = tk.Label(self.org_frame,text='No file loaded ...')
        self.fileendValue.grid(row=3,column=2,columnspan=1)
        # things in the fifth row of the GUI
        plotstartLabel = tk.Label(self.org_frame, text='Start date (YYYY-MM-DD)')
        plotstartLabel.grid(row=4,column=1,columnspan=1)
        self.plotstartEntry = tk.Entry(self.org_frame)
        self.plotstartEntry.grid(row=4,column=2,columnspan=1)
        # things in row sixth of the GUI
        plotendLabel = tk.Label(self.org_frame, text='End date   (YYYY-MM-DD)')
        plotendLabel.grid(row=5,column=1,columnspan=1)
        self.plotendEntry = tk.Entry(self.org_frame)
        self.plotendEntry.grid(row=5,column=2,columnspan=1)
        # things in the seventh row of the GUI
        closeplotwindowsButton = tk.Button (self.org_frame, text="Close plot windows", command=self.do_closeplotwindows )
        closeplotwindowsButton.grid(row=6,column=0,columnspan=1)
        plotL1L2Button = tk.Button (self.org_frame, text="Plot L1 & L2 Data", command=self.do_plotL1L2 )
        plotL1L2Button.grid(row=6,column=1,columnspan=1)
        plotL3L3Button = tk.Button (self.org_frame, text="Plot L3 Data", command=self.do_plotL3L3 )
        plotL3L3Button.grid(row=6,column=2,columnspan=1)
        plotL3L3Button = tk.Button (self.org_frame, text="Plot L3 & L4 Data", command=self.do_plotL3L4 )
        plotL3L3Button.grid(row=6,column=3,columnspan=1)
        # things in the eigth row of the GUI
        quitButton = tk.Button (self.org_frame, text='Quit', command=self.do_quit )
        quitButton.grid(row=7,column=0,columnspan=1)
        savexL2Button = tk.Button (self.org_frame, text='Write L2 Excel file', command=self.do_savexL2 )
        savexL2Button.grid(row=7,column=1,columnspan=1)
        savexL3Button = tk.Button (self.org_frame, text='Write L3 Excel file', command=self.do_savexL3 )
        savexL3Button.grid(row=7,column=2,columnspan=1)
        savexL4Button = tk.Button (self.org_frame, text='Write L4 Excel file', command=self.do_savexL4 )
        savexL4Button.grid(row=7,column=3,columnspan=1)
        # other things in the GUI
        self.progress = tk.Label(self.org_frame, text='Waiting for input ...')
        self.progress.grid(row=8,column=0,columnspan=2,sticky="W")
        # now we put together the menu, "File" first
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar,tearoff=0)
        filemenu.add_command(label="Concatenate netCDF",command=self.option_not_implemented)
        filemenu.add_command(label="List netCDF contents",command=self.option_not_implemented)
        filemenu.add_command(label="nc to xls",command=self.option_not_implemented)
        filemenu.add_command(label="xls to nc",command=self.option_not_implemented)
        filemenu.add_separator()
        filemenu.add_command(label="Quit",command=self.do_quit)
        menubar.add_cascade(label="File",menu=filemenu)
        # now the "Run" menu
        runmenu = tk.Menu(menubar,tearoff=0)
        runmenu.add_command(label="Read L1 Excel file",command=self.do_xl2ncL1)
        runmenu.add_command(label="Do L2 QA/QC",command=self.do_l2qc)
        runmenu.add_command(label="Do L3 processing",command=self.do_l3qc)
        runmenu.add_command(label="Do L4 gap filling",command=self.do_l4qc)
        runmenu.add_command(label="Do L5 partitioning",command=self.option_not_implemented)
        menubar.add_cascade(label="Run",menu=runmenu)
        # then the "Plot" menu
        plotmenu = tk.Menu(menubar,tearoff=0)
        plotmenu.add_command(label="Plot L1 & L2",command=self.do_plotL1L2)
        plotmenu.add_command(label="Plot L3",command=self.do_plotL3L3)
        plotmenu.add_command(label="Plot L3 & L4",command=self.do_plotL3L4)
        plotmenu.add_command(label="Plot L5",command=self.option_not_implemented)
        pltsummenu = tk.Menu(menubar,tearoff=0)
        pltsummenu.add_command(label="Fingerprint",command=self.option_not_implemented)
        pltsummenu.add_command(label="Full check",command=self.option_not_implemented)
        pltsummenu.add_command(label="Quick check",command=self.option_not_implemented)
        pltsummenu.add_command(label="Years check",command=self.option_not_implemented)
        plotmenu.add_cascade(label="Summary",menu=pltsummenu)
        plotmenu.add_separator()
        plotmenu.add_command(label="Close plots",command=self.do_closeplotwindows)
        menubar.add_cascade(label="Plot",menu=plotmenu)
        # and the "Utilities" menu
        utilsmenu = tk.Menu(menubar,tearoff=0)
        utilsmenu.add_command(label="Climatology",command=self.do_climatology)
        menubar.add_cascade(label="Utilities",menu=utilsmenu)
        # followed by the "u*" menu
        ustarmenu = tk.Menu(menubar,tearoff=0)
        ustarmenu.add_command(label="Reichstein",command=self.option_not_implemented)
        ustarmenu.add_command(label="Change Point Detection",command=self.option_not_implemented)
        ustarmenu.add_command(label="Cleverly",command=self.option_not_implemented)
        menubar.add_cascade(label="u* threshold",menu=ustarmenu)
        # and lastly the partitioning menu
        partitionmenu = tk.Menu(menubar,tearoff=0)
        partitionmenu.add_command(label="Lloyd-Taylor",command=self.option_not_implemented)
        partitionmenu.add_command(label="Lasslop",command=self.option_not_implemented)
        partitionmenu.add_command(label="ANN",command=self.option_not_implemented)
        menubar.add_cascade(label="Respiration",menu=partitionmenu)

        self.config(menu=menubar)

    def do_closeplotwindows(self):
        """
            Close plot windows
            """
        import matplotlib
        self.do_progress(text='Closing plot windows ...')             # tell the user what we're doing
        log.info(' Closing plot windows ...')
        fig_numbers = [n.num for n in matplotlib._pylab_helpers.Gcf.get_all_fig_managers()]
        log.info('  Closing plot windows: '+str(fig_numbers))
        for n in fig_numbers:
            matplotlib.pyplot.close(n)
        self.do_progress(text='Waiting for input ...')             # tell the user what we're doing
        log.info(' Waiting for input ...')

    def do_l2qc(self):
        """
            Call qcls.l2qc function
            Performs L2 QA/QC processing on raw data
            Outputs L2 netCDF file to ncData folder
            
            ControlFiles:
                L2_year.txt
                or
                L2.txt
            
            ControlFile contents (see ControlFile/Templates/L2.txt for example):
                [General]:
                    Enter list of functions to be performed
                [Files]:
                    L1 input file name and path
                    L2 output file name and path
                [Variables]:
                    Variable names and parameters for:
                        Range check to set upper and lower rejection limits
                        Diurnal check to reject observations by time of day that
                            are outside specified standard deviation limits
                        Timestamps for excluded dates
                        Timestamps for excluded hours
                [Plots]:
                    Variable lists for plot generation
            """
        self.do_progress(text='Load L2 Control File ...')
        self.cf = qcio.load_controlfile(path='controlfiles')
        if len(self.cf)==0: self.do_progress(text='Waiting for input ...'); return
        infilename = qcio.get_infilename_from_cf(self.cf)
        if len(infilename)==0: self.do_progress(text='An error occurred, check the console ...'); return
        self.do_progress(text='Doing L2 QC ...')
        self.ds1 = qcio.nc_read_series(infilename)
        if len(self.ds1.series.keys())==0: self.do_progress(text='An error occurred, check the console ...'); del self.ds1; return
        self.update_startenddate(str(self.ds1.series['DateTime']['Data'][0]),
                                 str(self.ds1.series['DateTime']['Data'][-1]))
        self.ds2 = qcls.l2qc(self.cf,self.ds1)
        log.info(' Finished L2 QC process')
        self.do_progress(text='Finished L2 QC process')
        self.do_progress(text='Saving L2 QC ...')                     # put up the progress message
        outfilename = qcio.get_outfilename_from_cf(self.cf)
        if len(outfilename)==0: self.do_progress(text='An error occurred, check the console ...'); return
        ncFile = qcio.nc_open_write(outfilename)
        qcio.nc_write_series(ncFile,self.ds2)                                  # save the L2 data
        self.do_progress(text='Finished saving L2 QC data')              # tdo_progressell the user we are done
        log.info(' Finished saving L2 QC data')

    def do_l3qc(self):
        """
            Call qcls.l3qc_sitename function
            Performs L3 Corrections and QA/QC processing on L2 data
            Outputs L3 netCDF file to ncData folder
            Outputs L3 netCDF file to OzFlux folder
            
            Available corrections:
            * corrections requiring ancillary measurements or samples
              marked with an asterisk
                Linear correction
                    fixed slope
                    linearly shifting slope
                Conversion of virtual temperature to actual temperature
                2D Coordinate rotation
                Massman correction for frequency attenuation*
                Webb, Pearman and Leuning correction for flux effects on density
                    measurements
                Conversion of virtual heat flux to actual heat flux
                Correction of soil moisture content to empirical calibration
                    curve*
                Addition of soil heat storage to ground ground heat flux*
            
            ControlFiles:
                L3_year.txt
                or
                L3a.txt
            
            ControlFile contents (see ControlFile/Templates/L3.txt for example):
                [General]:
                    Python control parameters
                [Files]:
                    L2 input file name and path
                    L3 output file name and ncData folder path
                    L3 OzFlux output file name and OzFlux folder path
                [Massman] (where available):
                    Constants used in frequency attenuation correction
                        zmd: instrument height (z) less zero-plane displacement
                            height (d), m
                        z0: aerodynamic roughness length, m
                        angle: angle from CSAT mounting point between CSAT and
                            IRGA mid-path, degrees
                        CSATarm: distance from CSAT mounting point to CSAT
                            mid-path, m
                        IRGAarm: distance from CSAT mounting point to IRGA
                            mid-path, m
                [Soil]:
                    Constants used in correcting Fg for storage and in empirical
                    corrections of soil water content 
                        FgDepth: Heat flux plate depth, m
                        BulkDensity: Soil bulk density, kg/m3
                        OrganicContent: Soil organic content, fraction
                        SwsDefault
                        Constants for empirical corrections using log(sensor)
                            and exp(sensor) functions (SWC_a0, SWC_a1, SWC_b0,
                            SWC_b1, SWC_t, TDR_a0, TDR_a1, TDR_b0, TDR_b1,
                            TDR_t)
                        Variable and attributes lists (empSWCin, empSWCout,
                            empTDRin, empTDRout, linTDRin, SWCattr, TDRattr)
                [Output]:
                    Variable subset list for OzFlux output file
                [Variables]:
                    Variable names and parameters for:
                        Range check to set upper and lower rejection limits
                        Diurnal check to reject observations by time of day that
                            are outside specified standard deviation limits
                        Timestamps, slope, and offset for Linear correction
                [Plots]:
                    Variable lists for plot generation
            """
        self.cf = qcio.load_controlfile(path='controlfiles')
        if len(self.cf)==0: self.do_progress(text='Waiting for input ...'); return
        infilename = qcio.get_infilename_from_cf(self.cf)
        if len(infilename)==0: self.do_progress(text='An error occurred, check the console ...'); return
        self.ds2 = qcio.nc_read_series(infilename)
        if len(self.ds2.series.keys())==0: self.do_progress(text='An error occurred, check the console ...'); del self.ds2; return
        self.update_startenddate(str(self.ds2.series['DateTime']['Data'][0]),
                                 str(self.ds2.series['DateTime']['Data'][-1]))
        self.do_progress(text='Doing L3 QC & Corrections ...')
        self.ds3 = qcls.l3qc(self.cf,self.ds2)
        self.do_progress(text='Finished L3')
        txtstr = ' Finished L3: Standard processing for site: '
        txtstr = txtstr+self.ds3.globalattributes['site_name'].replace(' ','')
        log.info(txtstr)
        self.do_progress(text='Saving L3 QC & Corrected NetCDF data ...')       # put up the progress message
        outfilename = qcio.get_outfilename_from_cf(self.cf)
        if len(outfilename)==0: self.do_progress(text='An error occurred, check the console ...'); return
        ncFile = qcio.nc_open_write(outfilename)
        outputlist = qcio.get_outputlist_from_cf(self.cf,'nc')
        qcio.nc_write_series(ncFile,self.ds3,outputlist=outputlist)             # save the L3 data
        self.do_progress(text='Finished saving L3 QC & Corrected NetCDF data')  # tell the user we are done
        log.info(' Finished saving L3 QC & Corrected NetCDF data')

    def do_l4qc(self):
        """
            Call qcls.l4qc_gapfill function
            Performs L4 gap filling on L3 met data
            or
            Ingests L4 gap filled fluxes performed in external SOLO-ANN and c
                omputes daily sums
            Outputs L4 netCDF file to ncData folder
            Outputs L4 netCDF file to OzFlux folder
            
            ControlFiles:
                L4_year.txt
                or
                L4b.txt
            
            ControlFile contents (see ControlFile/Templates/L4.txt and
            ControlFile/Templates/L4b.txt for examples):
                [General]:
                    Python control parameters (SOLO)
                    Site characteristics parameters (Gap filling)
                [Files]:
                    L3 input file name and path (Gap filling)
                    L4 input file name and path (SOLO)
                    L4 output file name and ncData folder path (both)
                    L4 OzFlux output file name and OzFlux folder path
                [Variables]:
                    Variable subset list for OzFlux output file (where
                        available)
            """
        self.cf = qcio.load_controlfile(path='controlfiles')
        if len(self.cf)==0: self.do_progress(text='Waiting for input ...'); return
        infilename = qcio.get_infilename_from_cf(self.cf)
        if len(infilename)==0: self.do_progress(text='An error occurred, check the console ...'); return
        self.ds3 = qcio.nc_read_series(infilename)
        if len(self.ds3.series.keys())==0: self.do_progress(text='An error occurred, check the console ...'); del self.ds3; return
        self.ds3.globalattributes['controlfile_name'] = self.cf['controlfile_name']
        self.update_startenddate(str(self.ds3.series['DateTime']['Data'][0]),
                                 str(self.ds3.series['DateTime']['Data'][-1]))
        sitename = self.ds3.globalattributes['site_name']
        self.do_progress(text='Doing L4 QC: '+sitename+' ...')
        self.ds4 = qcls.l4qc(self.cf,self.ds3)
        self.do_progress(text='Finished L4: '+sitename)
        log.info(' Finished L4: '+sitename)
        self.do_progress(text='Saving L4 Gap Filled NetCDF data ...')           # put up the progress message
        outfilename = qcio.get_outfilename_from_cf(self.cf)
        if len(outfilename)==0: self.do_progress(text='An error occurred, check the console ...'); return
        ncFile = qcio.nc_open_write(outfilename)
        outputlist = qcio.get_outputlist_from_cf(self.cf,'nc')
        qcio.nc_write_series(ncFile,self.ds4,outputlist=outputlist)             # save the L4 data
        self.do_progress(text='Finished saving L4 gap filled NetCDF data')      # tell the user we are done
        log.info(' Finished saving L4 gap filled NetCDF data')

    def do_plotL1L2(self):
        """
            Plot L1 (raw) and L2 (QA/QC) data in blue and red, respectively
            
            Control File for do_l2qc function used.
            If L2 Control File not loaded, requires control file selection.
            """
        if 'ds1' not in dir(self) or 'ds2' not in dir(self):
            self.cf = qcio.load_controlfile(path='controlfiles')
            if len(self.cf)==0: self.do_progress(text='Waiting for input ...'); return
            l1filename = qcio.get_infilename_from_cf(self.cf)
            if len(l1filename)==0: return
            self.ds1 = qcio.nc_read_series(l1filename)
            if len(self.ds1.series.keys())==0: self.do_progress(text='An error occurred, check the console ...'); del self.ds1; return
            l2filename = qcio.get_outfilename_from_cf(self.cf)
            self.ds2 = qcio.nc_read_series(l2filename)
            if len(self.ds2.series.keys())==0: self.do_progress(text='An error occurred, check the console ...'); del self.ds2; return
            self.update_startenddate(str(self.ds1.series['DateTime']['Data'][0]),
                                     str(self.ds1.series['DateTime']['Data'][-1]))
        self.do_progress(text='Plotting L1 & L2 QC ...')
        cfname = self.ds2.globalattributes['controlfile_name']
        self.cf = qcio.get_controlfilecontents(cfname)
        for nFig in self.cf['Plots'].keys():
            si = qcutils.GetDateIndex(self.ds1.series['DateTime']['Data'],self.plotstartEntry.get(),
                                      ts=self.ds1.globalattributes['time_step'],default=0,match='exact')
            ei = qcutils.GetDateIndex(self.ds1.series['DateTime']['Data'],self.plotendEntry.get(),
                                      ts=self.ds1.globalattributes['time_step'],default=-1,match='exact')
            plt_cf = self.cf['Plots'][str(nFig)]
            if 'Type' in plt_cf.keys():
                if str(plt_cf['Type']).lower() =='xy':
                    self.do_progress(text='Plotting L1 and L2 XY ...')
                    qcplot.plotxy(self.cf,nFig,plt_cf,self.ds1,self.ds2,si,ei)
                else:
                    self.do_progress(text='Plotting L1 and L2 QC ...')
                    qcplot.plottimeseries(self.cf,nFig,self.ds1,self.ds2,si,ei)
            else:
                self.do_progress(text='Plotting L1 and L2 QC ...')
                qcplot.plottimeseries(self.cf,nFig,self.ds1,self.ds2,si,ei)
        self.do_progress(text='Finished plotting L1 and L2')
        log.info(' Finished plotting L1 and L2, check the GUI')

    def do_plotL3L3(self):
        """
            Plot L3 (QA/QC and Corrected) data
            
            Control File for do_l3qc function used.
            If L3 Control File not loaded, requires control file selection.
            """
        if 'ds3' not in dir(self):
            self.cf = qcio.load_controlfile(path='controlfiles')
            if len(self.cf)==0: self.do_progress(text='Waiting for input ...'); return
            l3filename = qcio.get_outfilename_from_cf(self.cf)
            self.ds3 = qcio.nc_read_series(l3filename)
            if len(self.ds3.series.keys())==0: self.do_progress(text='An error occurred, check the console ...'); del self.ds3; return
            self.update_startenddate(str(self.ds3.series['DateTime']['Data'][0]),
                                     str(self.ds3.series['DateTime']['Data'][-1]))
        self.do_progress(text='Plotting L3 QC ...')
        cfname = self.ds3.globalattributes['controlfile_name']
        self.cf = qcio.get_controlfilecontents(cfname)
        for nFig in self.cf['Plots'].keys():
            si = qcutils.GetDateIndex(self.ds3.series['DateTime']['Data'],self.plotstartEntry.get(),
                                      ts=self.ds3.globalattributes['time_step'],default=0,match='exact')
            ei = qcutils.GetDateIndex(self.ds3.series['DateTime']['Data'],self.plotendEntry.get(),
                                      ts=self.ds3.globalattributes['time_step'],default=-1,match='exact')
            plt_cf = self.cf['Plots'][str(nFig)]
            if 'Type' in plt_cf.keys():
                if str(plt_cf['Type']).lower() =='xy':
                    self.do_progress(text='Plotting L3 XY ...')
                    qcplot.plotxy(self.cf,nFig,plt_cf,self.ds3,self.ds3,si,ei)
                else:
                    self.do_progress(text='Plotting L3 QC ...')
                    SeriesList = ast.literal_eval(plt_cf['Variables'])
                    qcplot.plottimeseries(self.cf,nFig,self.ds3,self.ds3,si,ei)
            else:
                self.do_progress(text='Plotting L3 QC ...')
                qcplot.plottimeseries(self.cf,nFig,self.ds3,self.ds3,si,ei)
        self.do_progress(text='Finished plotting L3')
        log.info(' Finished plotting L3, check the GUI')

    def do_plotL3L4(self):
        """
            Plot L3 (QA/QC and Corrected) and L4 (Gap Filled) data in blue and
                red, respectively
            
            Control File for do_l4qc function used.
            If L4 Control File not loaded, requires control file selection.
            """
        if 'ds3' not in dir(self) or 'ds4' not in dir(self):
            self.cf = qcio.load_controlfile(path='controlfiles')
            if len(self.cf)==0:
                self.do_progress(text='Waiting for input ...')
                return
            l3filename = qcio.get_infilename_from_cf(self.cf)
            if len(l3filename)==0: self.do_progress(text='An error occurred, check the console ...'); return
            self.ds3 = qcio.nc_read_series(l3filename)
            if len(self.ds3.series.keys())==0: self.do_progress(text='An error occurred, check the console ...'); del self.ds3; return
            l4filename = qcio.get_outfilename_from_cf(self.cf)
            self.ds4 = qcio.nc_read_series(l4filename)
            if len(self.ds4.series.keys())==0: self.do_progress(text='An error occurred, check the console ...'); del self.ds4; return
            self.update_startenddate(str(self.ds3.series['DateTime']['Data'][0]),
                                     str(self.ds3.series['DateTime']['Data'][-1]))
        self.do_progress(text='Plotting L3 and L4 QC ...')
        cfname = self.ds4.globalattributes['controlfile_name']
        self.cf = qcio.get_controlfilecontents(cfname)
        for nFig in self.cf['Plots'].keys():
            si = qcutils.GetDateIndex(self.ds3.series['DateTime']['Data'],self.plotstartEntry.get(),
                                      ts=self.ds3.globalattributes['time_step'],default=0,match='exact')
            ei = qcutils.GetDateIndex(self.ds3.series['DateTime']['Data'],self.plotendEntry.get(),
                                      ts=self.ds3.globalattributes['time_step'],default=-1,match='exact')
            qcplot.plottimeseries(self.cf,nFig,self.ds3,self.ds4,si,ei)
        self.do_progress(text='Finished plotting L4')
        log.info(' Finished plotting L4, check the GUI')

    def do_progress(self,text):
        """
            Update progress message in QC Data GUI
            """
        self.progress.destroy()
        self.progress = tk.Label(self.org_frame, text=text)
        self.progress.grid(row=8,column=0,columnspan=2,sticky="W")
        self.update()

    def do_quit(self):
        """
            Close plot windows and quit QC Data GUI
            """
        import matplotlib
        self.do_progress(text='Closing plot windows ...')             # tell the user what we're doing
        log.info(' Closing plot windows ...')
        matplotlib.pyplot.close('all')
        self.do_progress(text='Quitting ...')                         # tell the user what we're doing
        log.info(' Quitting ...')
        self.quit()

    def do_savexL2(self):
        """
            Call nc2xl function
            Exports excel data from NetCDF file
            
            Outputs L2 Excel file containing Data and Flag worksheets
            """
        self.do_progress(text='Exporting L2 NetCDF -> Xcel ...')                     # put up the progress message
        qcio.nc2xl(self.cf)
        self.do_progress(text='Finished L2 Data Export')              # tell the user we are done
        log.info(' Finished saving L2 data')

    def do_savexL3(self):
        """
            Call nc2xl function
            Exports excel data from NetCDF file
            
            Outputs L3 Excel file containing Data and Flag worksheets
            """
        self.do_progress(text='Exporting L3 NetCDF -> Xcel ...')                     # put up the progress message
        qcio.nc2xl(self.cf)
        self.do_progress(text='Finished L3 Data Export')              # tell the user we are done
        log.info(' Finished saving L3 data')

    def do_savexL4(self):
        """
            Call nc2xl function
            Exports excel data from NetCDF file
            
            Outputs L4 Excel file containing Data and Flag worksheets
            """
        self.do_progress(text='Exporting L4 NetCDF -> Xcel ...')                     # put up the progress message
        qcio.nc2xl(self.cf)
        self.do_progress(text='Finished L4 Data Export')              # tell the user we are done
        log.info(' Finished saving L4 data')

    def do_xl2ncL1(self):
        """
        Calls do_xl2nc with in_level set to L1
            Level 1:
                Read L1 Excel workbook
                Generate flags for missing observations
                Output L1 netCDF file to ncData folder
                Control file: L1.txt
        """
        self.in_level = 'L1'
        self.do_xl2nc()
    
    def do_xl2ncL3(self):
        """
        Calls do_xl2nc with in_level set to L3
            Level 3:
                Ingest excel database with QA/QC and corrected fluxes
                Ingest flags generated in L3
                Outputs L3 netCDF file to ncData folder
                Control file: L3a_xl2nc_corrected
        """
        self.in_level = 'L3'
        self.do_xl2nc()

    def do_xl2ncL4(self):
        """
        Calls do_xl2nc with in_level set to L4
            Level 4:
                Ingest excel database with Gap Filled fluxes
                Ingest flags generated in L3 & L4
                Outputs L4 netCDF file to ncData folder
                Control file: L4a_xl2nc_gapfilled
        """
        self.in_level = 'L4'
        self.do_xl2nc()

    def do_xl2nc(self):
        """
        Calls qcio.xl2nc
        """
        self.do_progress(text='Loading control file ...')
        self.cf = qcio.load_controlfile(path='controlfiles')
        if len(self.cf)==0: self.do_progress(text='Waiting for input ...'); return
        self.do_progress(text='Reading Excel file & writing to netCDF')
        rcode = qcio.xl2nc(self.cf,self.in_level)
        if rcode==0:
            self.do_progress(text='Finished writing to netCDF ...')
            log.info(' Finished writing to netCDF ...')
        else:
            self.do_progress(text='An error occurred, check the console ...')

    def update_startenddate(self,startstr,endstr):
        """
            Read start and end timestamps from data and report in QC Data GUI
            """
        self.filestartValue.destroy()
        self.fileendValue.destroy()
        self.filestartValue = tk.Label(self.org_frame,text=startstr)
        self.filestartValue.grid(row=3,column=1,columnspan=1)
        self.fileendValue = tk.Label(self.org_frame,text=endstr)
        self.fileendValue.grid(row=3,column=2,columnspan=1)
        self.update()
    
    def do_climatology(self):
        """
        Calls qcclim.climatology
        """
        self.do_progress(text='Loading control file ...')
        cf = qcio.load_controlfile(path='controlfiles')
        if len(cf)==0: self.do_progress(text='Waiting for input ...'); return
        self.do_progress(text='Doing the climatology')
        qcclim.climatology(cf)
        self.do_progress(text='Finished climatology')
        log.info(' Finished climatology')

if __name__ == "__main__":
    log = qcutils.startlog('qc','logfiles/qc.log')
    qcGUI = qcgui(None)
    main_title = cfg.version_name+' Main GUI '+cfg.version_number
    qcGUI.title(main_title)
    qcGUI.mainloop()
    qcGUI.destroy()

    log.info('QC: All done')
