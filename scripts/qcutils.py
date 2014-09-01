# the following line needed for unicode character in convert_anglestring
# -*- coding: latin-1 -*-
import ast
import constants as c
import datetime
import dateutil
import logging
import math
import meteorologicalfunctions as mf
import numpy
import os
import pytz
import sys
import time
import Tkinter,tkSimpleDialog
import xlrd
import xlwt

log = logging.getLogger('qc.utils')

def bp(fx,tao):
    """
    Function to calculate the b and p coeficients of the Massman frequency correction.
    """
    bp = 2 * c.Pi * fx * tao
    return bp

def cfkeycheck(cf,Base='Variables',ThisOne=[],key=[]):
    if len(ThisOne) == 0:
        return
    if len(key) == 0:
        if Base in cf.keys() and ThisOne in cf[Base].keys():
            return ThisOne in cf[Base].keys()
        else:
            return
    else:
        if Base in cf.keys() and ThisOne in cf[Base].keys():
            return key in cf[Base][ThisOne].keys()
        else:
            return

def cfoptionskey(cf,Key='',default=False):
    if 'Options' in cf:
        if Key in cf['Options']:
            if str(cf['Options'][Key]).lower()=="true" or str(cf['Options'][Key]).lower()=="yes":
                returnValue = True
            else:
                returnValue = False
        else:
            returnValue = default
    else:
        returnValue = default
    return returnValue

def CheckQCFlags(ds):
    """
    Purpose:
     Make sure that all values of -9999 in a data series have a non-zero QC flag value.
    Usage:
     qcutils.CheckQCFlags(ds)
    Author: PRI
    Date: August 2014
    """
    for ThisOne in ds.series.keys():
        data = numpy.ma.masked_values(ds.series[ThisOne]["Data"],-9999)
        flag = numpy.ma.masked_equal(ds.series[ThisOne]["Flag"],0)
        mask = data.mask&flag.mask
        index = numpy.ma.where(mask==True)[0]
        ds.series[ThisOne]["Flag"][index] = numpy.int32(8)

def CheckTimeStep(ds,fix='gaps'):
    """
    Purpose:
     Checks the datetime series in the data structure ds to see if there are
     any missing time stamps.  If missing time stamps are found, this routine
     will print a message to the screen and log file and then check to see
     if all gaps in the datetime series are multiples of the time step.  If
     not, the routine prints a message to the screen and the log file.
     This function returns a logical variable that is true if any gaps exist
     in the time stamp.
    Useage:
     has_gaps = CheckTimeSTep(ds)
     if has_gaps:
         <do something about missing time stamps>
    Author: PRI
    Date: April 2013
    """
    has_gaps = False
    ts = int(ds.globalattributes['time_step'])
    xldt = ds.series['xlDateTime']['Data']
    dt = numpy.zeros(len(xldt))
    dt[0] = ts
    dt[1:-1] = (1440*(xldt[1:-1]-xldt[0:-2])+0.5).astype(int)
    dt[-1] = (1440*(xldt[-1]-xldt[-2])+0.5).astype(int)
    index = numpy.where(dt!=ts)[0]
    if len(index)!=0:
        has_gaps = True
        log.error(' CheckTimeStep: '+str(len(index))+ ' gaps found in the time series')
        dtmin = numpy.min(dt)
        dtmax = numpy.max(dt)
        if dtmin < ts:
            print dtmin,ds.series['DateTime']['Data'][numpy.where(dt==dtmin)[0]-3],numpy.where(dt==dtmin)[0]-3
            print dtmin,ds.series['DateTime']['Data'][numpy.where(dt==dtmin)[0]-2],numpy.where(dt==dtmin)[0]-2
            print dtmin,ds.series['DateTime']['Data'][numpy.where(dt==dtmin)[0]-1],numpy.where(dt==dtmin)[0]-1
            print dtmin,ds.series['DateTime']['Data'][numpy.where(dt==dtmin)[0]],numpy.where(dt==dtmin)[0]
            print dtmin,ds.series['DateTime']['Data'][numpy.where(dt==dtmin)[0]+1],numpy.where(dt==dtmin)[0]+1
            log.critical(' CheckTimeStep: duplicate or overlapping times found, fix the L1 spreadsheet')
            sys.exit()
        if numpy.min(numpy.mod(dt,ts))!=0 or numpy.max(numpy.mod(dt,ts))!=0:
            log.critical(' CheckTimeStep: time gaps are not multiples of the time step ('+str(ts)+'), fix the L1 spreadsheet')
            sys.exit()
        if dtmax > ts:
            log.info(' CheckTimeStep: one or more time gaps found')
            if fix.lower()=='gaps':
                log.info(' CheckTimeStep: calling FixTimeGaps to fix time gaps')
                FixTimeGaps(ds)
    else:
        log.info(' CheckTimeStep: no time gaps found')
    return has_gaps

def ConvertCO2Units(cf,ds,Cc='Cc'):
    Cc_units_out = "mg/m3"            # default value
    Cc_units_in = ds.series[Cc]['Attr']['units']
    if 'Options' in cf:
        if 'CO2Units' in cf['Options']:
            Cc_units_out = str(cf['Options']['CO2Units'])
    if Cc_units_out!=Cc_units_in:
        log.info(' Converting CO2 concentration from '+Cc_units_in+' to '+Cc_units_out)
        if Cc_units_out=="umol/mol" and Cc_units_in=="mg/m3":
            c_mgpm3,flag,attr = GetSeriesasMA(ds,Cc)
            T,f,a = GetSeriesasMA(ds,'Ta')
            p,f,a = GetSeriesasMA(ds,'ps')
            c_ppm = mf.co2_ppmfrommgpm3(c_mgpm3,T,p)
            long_name = attr["long_name"]+", converted to umol/mol"
            attr = MakeAttributeDictionary(long_name=long_name,units=Cc_units_out)
            CreateSeries(ds,Cc,c_ppm,Flag=flag,Attr=attr)
        elif Cc_units_out=="mg/m3" and Cc_units_in=="umol/mol":
            c_ppm,flag,attr = GetSeriesasMA(ds,Cc)
            T,f,a = GetSeriesasMA(ds,'Ta')
            p,f,a = GetSeriesasMA(ds,'ps')
            c_mgpm3 = mf.co2_mgpm3fromppm(c_ppm,T,p)
            long_name = attr["long_name"]+", converted to mg/m3"
            attr = MakeAttributeDictionary(long_name=long_name,units=Cc_units_out)
            CreateSeries(ds,Cc,c_mgpm3,Flag=flag,Attr=attr)
        else:
            log.info('  ConvertCO2Units: input or output units for CO2 concentration not recognised')

def ConvertFcUnits(cf,ds,Fc='Fc',Fc_storage='Fc_storage'):
    if 'Options' not in cf: return
    if 'FcUnits' not in cf['Options']: return
    # the user may want to change the units of Fc and Fc_storage
    Fc_units_out = str(cf['Options']['FcUnits'])
    # convert units of Fc if required
    if Fc in ds.series.keys():
        Fc_units_in = ds.series[Fc]['Attr']['units']
        if Fc_units_out!=Fc_units_in:
            log.info(' Converting CO2 flux from '+Fc_units_in+' to '+Fc_units_out)
            if Fc_units_out=="umol/m2/s" and Fc_units_in=="mg/m2/s":
                Fc_mgpm2ps,flag,attr = GetSeriesasMA(ds,Fc)
                Fc_umolpm2ps = mf.Fc_umolpm2psfrommgpm2ps(Fc_mgpm2ps)
                long_name = attr["long_name"]+', converted to umol/m2/s'
                attr =MakeAttributeDictionary(long_name=long_name,units=Fc_units_out)
                CreateSeries(ds,Fc,Fc_umolpm2ps,Flag=flag,Attr=attr)
            elif Fc_units_out=="mg/m2/s" and Fc_units_in=="umol/m2/s":
                Fc_umolpm2ps,f,a = GetSeriesasMA(ds,Fc)
                Fc_mgpm2ps = mf.Fc_mgpm2psfromumolpm2ps(Fc_umolpm2ps)
                long_name = attr["long_name"]+', converted to mg/m2/s'
                attr = MakeAttributeDictionary(long_name=long_name,units=Fc_units_out)
                CreateSeries(ds,Fc,Fc_mgpm2ps,Flag=flag,Attr=attr)
            else:
                log.info('  ConvertFcUnits: input or output units for Fc unrecognised')
    # convert units of Fc_storage if required, just go with boiler plate for now
    if Fc_storage in ds.series.keys():
        Fc_storage_units_in = ds.series[Fc_storage]['Attr']['units']
        if Fc_units_out!=Fc_storage_units_in:
            log.info(' Converting CO2 storage flux from '+Fc_storage_units_in+' to '+Fc_units_out)
            if Fc_units_out=="umol/m2/s" and Fc_storage_units_in=="mg/m2/s":
                Fc_storage_mgpm2ps,flag,attr = GetSeriesasMA(ds,Fc_storage)
                Fc_storage_umolpm2ps = mf.Fc_umolpm2psfrommgpm2ps(Fc_storage_mgpm2ps)
                long_name = attr["long_name"]+", converted to umol/m2/s"
                attr =MakeAttributeDictionary(long_name=long_name,units=Fc_units_out)
                CreateSeries(ds,Fc_storage,Fc_storage_umolpm2ps,Flag=flag,Attr=attr)
            elif Fc_units_out=="mg/m2/s" and Fc_storage_units_in=="umol/m2/s":
                Fc_storage_umolpm2ps,f,a = GetSeriesasMA(ds,Fc_storage)
                Fc_storage_mgpm2ps = mf.Fc_mgpm2psfromumolpm2ps(Fc_storage_umolpm2ps)
                long_name = attr["long_name"]+", converted to mg/m2/s"
                attr = MakeAttributeDictionary(long_name=long_name,units=Fc_units_out)
                CreateSeries(ds,Fc_storage,Fc_storage_mgpm2ps,Flag=flag,Attr=attr)
            else:
                log.info('  ConvertFcUnits: input or output units for Fc_storage unrecognised')

def convert_anglestring(anglestring):
    """
    Purpose:
     Attempt to convert an angle string to a float.
    Usage:
     a = qcutils.convert_anglestring(astr)
     Acceptable input formats:
      astr = '''34 12' 24" S'''
      astr = '''34 12 24S'''
      astr = '''34 12'24.123"S''
      astr = '''34.123 S'''
      astr = '''-34.123'''
    """
    quadlist=["N","E","S","W"]
    direction = {'N':1, 'S':-1, 'E': 1, 'W':-1}
    try:
        # simple casting may work, who knows?
        return float(anglestring)
    except ValueError:
        # replace the degrees, minutes and seconds symbols with spaces
        new = anglestring.replace(u'�',' ').replace('\'',' ').replace('"',' ')
        # check there is a space between the quadrant letter (assumed to be one of N, E, W or S)
        # and the next character to the left
        # find out which of N, E, S, or W is in the string
        for item in quadlist:
            if item in new: quadletter=item
        # now get the index of this character in the string
        i=new.index(quadletter)
        # check that the next character to the left is a space character
        if new[i-1] != " ": new = new[0:i]+" "+new[i:]
        # now split the string on space characters
        new = new.split()
        # get the quadrant letter
        new_dir = new.pop()
        # make sure we have 3 parts
        new.extend([0,0,0])
        # return with the string converted to a float
        return (float(new[0])+float(new[1])/60.0+float(new[2])/3600.0) * direction[new_dir]    

def CreateSeries(ds,Label,Data,FList=None,Flag=None,Attr=None):
    """
    Create a series (1d array) of data in the data structure.
    
    If the series already exists in the data structure, data values and QC flags will be
    overwritten but attributes will be preserved.  However, the long_name and units attributes
    are treated differently.  The existing long_name will have long_name appended to it.  The
    existing units will be overwritten with units.
    
    This utility is the prefered method for creating or updating a data series because
    it implements a consistent method for creating series in the data structure.  Direct
    writes to the contents of the data structure are discouraged (unless PRI wrote the code:=P).
    """
    ds.series['_tmp_'] = {}                       # create a temporary series to avoid premature overwrites
    # put the data into the temporary series
    if numpy.ma.isMA(Data):
        ds.series['_tmp_']['Data'] = numpy.ma.filled(Data,float(c.missing_value))
    else:
        ds.series['_tmp_']['Data'] = numpy.array(Data)
    # copy or make the QC flag
    if Flag == None:
        ds.series['_tmp_']['Flag'] = MakeQCFlag(ds,FList)
    else:
        ds.series['_tmp_']['Flag'] = Flag
    # do the attributes
    ds.series['_tmp_']['Attr'] = {}
    if Label in ds.series.keys():                 # check to see if the series already exists
        for attr in ds.series[Label]['Attr']:     # if it does, copy the existing attributes
            if attr in Attr and ds.series[Label]['Attr'][attr]!=Attr[attr]:
                ds.series['_tmp_']['Attr'][attr] = Attr[attr]
            else:
                ds.series['_tmp_']['Attr'][attr] = ds.series[Label]['Attr'][attr]
    else:
        for item in Attr:
            ds.series['_tmp_']['Attr'][item] = Attr[item]
    ds.series[unicode(Label)] = ds.series['_tmp_']     # copy temporary series to new series
    del ds.series['_tmp_']                        # delete the temporary series

def CreateDatetimeRange(start,stop,step=datetime.timedelta(minutes=30)):
    '''
    Purpose:
     Create a series of datetimes between the "start" and "stop" datetimes
     and with a time step of "step".
    Useage:
     dt = ds.series['DateTime']['Data']
     ts = ds.globaleattributes['time_step']
     dt_evenlyspaced = CreateDatetimeRange(dt[0],dt[-1],step=datetime.timedelta(minutes=ts))]
    Author: PRI
    Date: December 2013
    '''
    result = []
    while start<stop:
        result.append(start)
        start = start + step
    return result

def file_exists(filename,mode="verbose"):
    if not os.path.exists(filename):
        if mode=="verbose":
            log.error(' File '+filename+' not found')
        return False
    else:
        return True

def FixTimeGaps(ds):
    """
    Purpose:
     Fix gaps in datetime series found by CheckTimeStep.
    Useage:
     has_gaps = CheckTimeStep(ds)
     if has_gaps:
         FixTimeGaps(ds)
    Author: PRI
    Date: April 2013
    """
    log.info(' FixTimeGaps: fixing time gaps')
    ts_minutes = int(ds.globalattributes['time_step'])
    ts_seconds = int(60*ts_minutes+0.5)
    xldt = ds.series['xlDateTime']['Data']
    #pydt = ds.series['DateTime']['Data']
    pydt = RoundDateTime(ds.series['DateTime']['Data'],dt=ts_minutes)
    # generate a series of datetime values with no gaps
    start = pydt[0]
    end = pydt[-1]
    delta = pydt[-1] - pydt[0]
    nts = ((86400*delta.days+delta.seconds)/ts_seconds)+1
    pydt_nogaps = [start+datetime.timedelta(minutes=i*ts_minutes) for i in range(0,nts)]
    nRecs = len(pydt_nogaps)
    # get the indices in the "no gaps" datetime series corresponding to datetime values in the
    # "gappy" datetime series
    dt_ind = []
    idx = -1
    for item in pydt:
        idx = pydt_nogaps.index(item,idx+1)
        dt_ind.append(idx)
    # get a series of Excel datetime values from the "no gaps" Python datetime values
    xldtlist = []
    datemode = 0
    if 'xl_datemode' in ds.globalattributes.keys():
        datemode = int(ds.globalattributes['xl_datemode'])
    for i in range(0,nts):
        xldt = xlrd.xldate.xldate_from_datetime_tuple((pydt_nogaps[i].year,pydt_nogaps[i].month,pydt_nogaps[i].day,
                                                       pydt_nogaps[i].hour,pydt_nogaps[i].minute,pydt_nogaps[i].second),datemode)
        xldtlist.append(xldt)
    # replace the "gappy" Excel and Python datetime values in the data structure
    ds.series['xlDateTime']['Data'] = numpy.array(xldtlist,dtype=numpy.float64)
    org_flag = ds.series['xlDateTime']['Flag'].astype(numpy.int32)
    ds.series['xlDateTime']['Flag'] = numpy.ones(nRecs,dtype=numpy.int32)
    ds.series['xlDateTime']['Flag'][dt_ind] = org_flag
    ds.series['DateTime']['Data'] = pydt_nogaps
    org_flag = ds.series['DateTime']['Flag'].astype(numpy.int32)
    ds.series['DateTime']['Flag'] = numpy.ones(nRecs,dtype=numpy.int32)
    ds.series['DateTime']['Flag'][dt_ind] = org_flag
    # replace the "gappy" year, month, day, hour, minute and second series in the data structure
    get_ymdhmsfromxldate(ds)
    # replace the "gappy" UTC datetime
    get_UTCfromlocaltime(ds)
    # update the global attribute containing the number of records
    ds.globalattributes['nc_nrecs'] = str(len(ds.series['xlDateTime']['Data']))
    # remove the datetime-related series from data structure
    DateTimeList = ["xlDateTime","xlDateTime_UTC","DateTime","DateTime_UTC",
                    "Year","Month","Day","Hour","Minute","Second","Hdh","Ddd"]
    SeriesList = ds.series.keys()
    for item in DateTimeList:
        if item in SeriesList: SeriesList.remove(item)
    # replace the "gappy" data with the "no gap" data
    for ThisOne in SeriesList:
        attr = GetAttributeDictionary(ds,ThisOne)
        org_data,org_flag,org_attr = GetSeriesasMA(ds,ThisOne)
        new_data = numpy.zeros(nRecs,dtype=numpy.float64) - float(9999)
        new_flag = numpy.ones(nRecs,dtype=numpy.int32)
        new_data[dt_ind] = org_data
        new_flag[dt_ind] = org_flag
        CreateSeries(ds,ThisOne,new_data,Flag=new_flag,Attr=attr)

def Fm(z, z0, L):
    ''' Integral form of the adiabatic correction to the wind speed profile.'''
    Fm = math.log(z/z0)                 # Neutral case
    if L<0:                             # Unstable case
        R0 = (1-c.gamma*z0/L)**0.25
        R1 = (1-c.gamma*z/L)**0.25
        x = ((R0+1)/(R1+1))**2
        Y = (R0*R0+1)/(R1*R1+1)
        w = z/z0
        V = 2 * numpy.arctan((R1-R0)/(1+R0*R1))
        Fm = math.log(w*Y*x)+V
    elif ((L>-200)|(L>200)):            # Neutral case
        Fm = math.log(z/z0)
    elif (z/L<=1):                      # Stable case, z < L
        x = math.log(z/z0)
        Y = c.beta*z/L
        Fm = x+Y
    elif ((z/L>1)&(z0/L<1)):            # Stable case, z > L > z0
        x = math.log(L/z0)
        Y = (1+c.beta)*math.log(z/L)
        Fm = x+c.beta+Y
    elif (z0/L>1):                      # Stable, L < z0
        Fm = (1+c.beta)*math.log(z/z0)
    else:
        print 'Error in function Fm'
    return Fm

def Fustar(T, Ah, p, Fh, u, z, z0, ustar):
#' Function used in iteration method to solve for ustar.
#' The function used is:
#'  ustar = u*k/Fm(z/L,z0/L)
#' where Fm is the integral form of the PHIm, the adiabatic
#' correction to the logarithmic wind speed profile.
#' Evaluate the function for ustar with this value for L.
    MO = mf.molen(T, Ah, p, ustar, Fh, fluxtype='sensible')
    Fustar = u*c.k/(Fm(z, z0, MO))
    return Fustar

def GetAverageSeriesKeys(cf,ThisOne):
    if incf(cf,ThisOne) and haskey(cf,ThisOne,'AverageSeries'):
        if 'Source' in cf['Variables'][ThisOne]['AverageSeries'].keys():
            alist = ast.literal_eval(cf['Variables'][ThisOne]['AverageSeries']['Source'])
        else:
            log.error('  GetAverageSeriesKeys: key "Source" not in control file AverageSeries section for '+ThisOne)
            alist = []
        if 'standard_name' in cf['Variables'][ThisOne]['AverageSeries'].keys():
            standardname = str(cf['Variables'][ThisOne]['AverageSeries']['standard_name'])
        else:
            standardname = "not defined"
    else:
        standardname = "not defined"
        log.info('  GetAverageSeriesKeys: '+ThisOne+ ' not in control file or it does not have the "AverageSeries" key')
        alist = []
    return alist, standardname

def GetAltName(cf,ds,ThisOne):
    '''
    Check to see if the specified variable name is in the data structure (ds).
    If it is, return the variable name unchanged.
    If it isn't, check the control file to see if an alternate name has been specified
     and return the alternate name if one exists.
    '''
    if ThisOne not in ds.series.keys():
        if ThisOne in cf['Variables'].keys():
            ThisOne = cf['Variables'][ThisOne]['AltVarName']
            if ThisOne not in ds.series.keys():
                log.error('GetAltName: alternate variable name not in ds')
        else:
            log.error('GetAltName: cant find ',ThisOne,' in ds or control file')
    return ThisOne

def GetAltNameFromCF(cf,ThisOne):
    '''
    Get an alternate variable name from the control file.
    '''
    if ThisOne in cf['Variables'].keys():
        if 'AltVarName' in cf['Variables'][ThisOne].keys():
            ThisOne = str(cf['Variables'][ThisOne]['AltVarName'])
        else:
            print 'GetAltNameFromCF: AltVarName key not in control file for '+str(ThisOne)
    else:
        print 'GetAltNameFromCF: '+str(ThisOne)+' not in control file'
    return ThisOne

def GetAttributeDictionary(ds,ThisOne):
    attr = {}
    # if series ThisOne is in the data structure
    if ThisOne in ds.series.keys():
        attr = ds.series[ThisOne]['Attr']
    else:
        attr = MakeAttributeDictionary()
    return attr

def GetcbTicksFromCF(cf,ThisOne):
    '''
    Get colour bar tick labels from the control file.
    '''
    if ThisOne in cf['Variables'].keys():
        if 'Ticks' in cf['Variables'][ThisOne].keys():
            Ticks = eval(cf['Variables'][ThisOne]['Ticks'])
        else:
            print 'GetcbTicksFromCF: Ticks key not in control file for '+str(ThisOne)
    else:
        print 'GetcbTicksFromCF: '+str(ThisOne)+' not in control file'
    return Ticks

def GetRangesFromCF(cf,ThisOne):
    '''
    Get lower and upper range limits from the control file.
    '''
    if ThisOne in cf['Variables'].keys():
        if 'Lower' in cf['Variables'][ThisOne].keys():
            lower = float(cf['Variables'][ThisOne]['Lower'])
        else:
            print 'GetRangesFromCF: Lower key not in control file for '+str(ThisOne)
            lower = None
        if 'Upper' in cf['Variables'][ThisOne].keys():
            upper = float(cf['Variables'][ThisOne]['Upper'])
        else:
            print 'GetRangesFromCF: Upper key not in control file for '+str(ThisOne)
            upper = None
    else:
        print 'GetRangesFromCF: '+str(ThisOne)+' not in control file'
        lower, upper = None
    return lower, upper

def GetDateIndex(datetimeseries,date,ts=30,default=0,match='exact'):
    '''
    PURPOSE:
     Return the index of a date/datetime string in an array of datetime objects
    USAGE:
     si = qcutils.GetDateIndex(datetimeseries,date_str,ts=30,default=0,match='exact')
    where
     datetimeseries - array of datetime objects
     date_str       - a date or date/time string in a format dateutils can parse
     ts             - time step for the data, optional (integer)
     default        - default value, optional (integer)
     match          - type of match (string) options are:
                      "exact"          - finds the specified datetime and returns
                                         the index
                      "startnextday"   - returns the index of the first time period
                                         in the next day
                      "endpreviousday" - returns the index of the last time period
                                         in the previous day
                NOTE: "startnextday" and "endpreviousday" can be used to pick
                    out time periods with an integer number of days
    AUTHOR: PRI
    '''
    try:
        if len(date)!=0:
            i = datetimeseries.index(dateutil.parser.parse(date))
        else:
            if default==-1:
                i = len(datetimeseries)-1
            else:
                i = default
    except ValueError:
        if default==-1:
            i = len(datetimeseries)-1
        else:
            i = default
    if match=='startnextday':
        while abs(datetimeseries[i].hour+float(datetimeseries[i].minute)/60-float(ts)/60)>c.eps:
            i = i + 1
    if match=='endpreviousday':
        while abs(datetimeseries[i].hour+float(datetimeseries[i].minute)/60)>c.eps:
            i = i - 1
    return i

def GetGlobalAttributeValue(cf,ds,ThisOne):
    if ThisOne not in ds.globalattributes.keys():
        if ThisOne in cf['General'].keys():
            ds.globalattributes[ThisOne] = cf['General'][ThisOne]
        else:
            log.error('  GetGlobalAttributeValue: global attribute '+ThisOne+' was not found in the netCDF file or in the control file')
            ds.globalattributes[ThisOne] = None
    return ds.globalattributes[ThisOne]

def GetMergeSeriesKeys(cf,ThisOne,section=''):
    if len(section)==0: section = 'Variables'
    if 'Source' in cf[section][ThisOne]['MergeSeries'].keys():
        mlist = ast.literal_eval(cf[section][ThisOne]['MergeSeries']['Source'])
    else:
        log.error('  GetMergeSeriesKeys: key "Source" not in control file MergeSeries section for '+ThisOne)
        mlist = []
    if 'standard_name' in cf[section][ThisOne]['MergeSeries'].keys():
        standardname = str(cf[section][ThisOne]['MergeSeries']['standard_name'])
    else:
        standardname = 'not defined'
    return mlist, standardname

def GetPlotTitleFromCF(cf, nFig):
    if 'Plots' in cf:
        if str(nFig) in cf['Plots']:
            if 'Title' in cf['Plots'][str(nFig)]:
                Title = str(cf['Plots'][str(nFig)]['Title'])
            else:
                print 'GetPlotTitleFromCF: Variables key not in control file for plot '+str(nFig)
        else:
            print 'GetPlotTitleFromCF: '+str(nFig)+' key not in Plots section of control file'
    else:
        print 'GetPlotTitleFromCF: Plots key not in control file'
    return Title

def GetPlotVariableNamesFromCF(cf, n):
    if 'Plots' in cf:
        if str(n) in cf['Plots']:
            if 'Variables' in cf['Plots'][str(n)]:
                SeriesList = eval(cf['Plots'][str(n)]['Variables'])
            else:
                print 'GetPlotVariableNamesFromCF: Variables key not in control file for plot '+str(n)
        else:
            print 'GetPlotVariableNamesFromCF: '+str(n)+' key not in Plots section of control file'
    else:
        print 'GetPlotVariableNamesFromCF: Plots key not in control file'
    return SeriesList

def GetSeries(ds,ThisOne,si=0,ei=-1,mode="truncate"):
    """ Returns the data, QC flag and attributes of a series from the data structure."""
    # number of records
    nRecs = int(ds.globalattributes["nc_nrecs"])
    # check the series requested is in the data structure
    if ThisOne in ds.series.keys():
        # series is in the data structure
        if isinstance(ds.series[ThisOne]['Data'],list):
            # return a list if the series is a list
            Series = list(ds.series[ThisOne]['Data'])
        elif isinstance(ds.series[ThisOne]['Data'],numpy.ndarray):
            # return a numpy array if series is an array
            Series = ds.series[ThisOne]['Data'].copy()
        # now get the QC flag
        if 'Flag' in ds.series[ThisOne].keys():
            # return the QC flag if it exists
            Flag = ds.series[ThisOne]['Flag'].copy()
            Flag = Flag.astype(numpy.int32)
        else:
            # create a QC flag if one does not exist
            Flag = numpy.zeros(nRecs,dtype=numpy.int32)
        # now get the attribute dictionary
        if "Attr" in ds.series[ThisOne].keys():
            Attr = GetAttributeDictionary(ds,ThisOne)
        else:
            Attr = MakeAttributeDictionary()
    else:
        # make an empty series if the requested series does not exist in the data structure
        Series,Flag,Attr = MakeEmptySeries(ds,ThisOne)
    # tidy up
    if mode=="truncate":
        # truncate to the requested start and end indices
        si = max(0,si)                  # clip start index at 0
        ei = min(nRecs,ei)              # clip end index to nRecs
        if ei==-1: ei = nRecs - 1       # trap ei = -1 values
        Series = Series[si:ei+1]        # truncate the data
        Flag = Flag[si:ei+1]            # truncate the QC flag
    elif mode=="pad":
        # pad with maiising data at the start and/or the end of the series
        if si<0 and ei>nRecs-1:
            # pad at the start
            Series = numpy.append(float(c.missing_value)*numpy.ones(abs(si),dtype=numpy.float64),Series)
            Flag = numpy.append(numpy.ones(*abs(si),dtype=numpy.int32),Flag)
            # pad at the end
            Series = numpy.append(Series,float(c.missing_value)*numpy.ones((ei-(nRecs-1)),dtype=numpy.float64))
            Flag = numpy.append(Flag,numpy.ones((ei-(nRecs-1)),dtype=numpy.int32))
        elif si<0 and ei<=nRecs-1:
            # pad at the start, truncate the end
            Series = numpy.append(float(c.missing_value)*numpy.ones(abs(si),dtype=numpy.float64),Series[:ei+1])
            Flag = numpy.append(numpy.ones(abs(si),dtype=numpy.int32),Flag[:ei+1])
        elif si>=0 and ei>nRecs-1:
            # truncate at the start, pad at the end
            Series = numpy.append(Series[si:],float(c.missing_value)*numpy.ones((ei-(nRecs-1)),numpy.float64))
            Flag = numpy.append(Flag[si:],numpy.ones((ei-(nRecs-1)),dtype=numpy.int32))
        elif si>=0 and ei<=nRecs-1:
            # truncate at the start and end
            if ei==-1: ei = nRecs - 1
            Series = Series[si:ei+1]
            Flag = Flag[si:ei+1]
        else:
            msg = 'GetSeries: unrecognised combination of si ('+str(si)+') and ei ('+str(ei)+')'
            raise ValueError(msg)
    else:
        raise ValueError('GetSeries: unrecognised mode option'+str(mode))
    return Series,Flag,Attr

def MakeEmptySeries(ds,ThisOne):
    nRecs = int(ds.globalattributes['nc_nrecs'])
    Series = float(c.missing_value)*numpy.ones(nRecs,dtype=numpy.float64)
    Flag = numpy.ones(nRecs,dtype=numpy.int32)
    Attr = MakeAttributeDictionary()
    return Series,Flag,Attr

def GetSeriesasMA(ds,ThisOne,si=0,ei=-1,mode="truncate"):
    '''
    PURPOSE:
     Returns a data series and the QC flag series from the data structure.
    USAGE:
     data,flag,attr = qcutils.GetSeriesasMA(ds,label,si=0,ei=-1)
    where the arguments are;
      ds    - the data structure (dict)
      label - label of the data series in ds (string)
      si    - start index (integer), default 0
      ei    - end index (integer), default -1
    and the returned values are;
      data - values for the requested series in ds
             (numpy masked array, float64)
      flag - QC flag for the requested series in ds
             (numpy masked array, int32)
      attr - attribute dictionary for series
    EXAMPLE:
     The code snippet below will return the incoming shortwave data values
     (Fsd) and the associated QC flag (f) as numpy masked arrays;
      ds = qcio.nc_read_series("HowardSprings_2011_L3.nc")
      Fsd,f,a = qcutils.GetSeriesasMA(ds,"Fsd")
    AUTHOR: PRI
    '''
    Series,Flag,Attr = GetSeries(ds,ThisOne,si,ei,mode)
    Series,WasND = SeriestoMA(Series)
    return Series,Flag,Attr

def GetUnitsFromds(ds, ThisOne):
    units = ds.series[ThisOne]['Attr']['units']
    return units

def get_cfsection(cf,series='',mode='quiet'):
    '''
    Find the section in the control file that contains an entry for the series "series".
    USEAGE:  section = qcutils.get_cfsection(cf,series=<series_name>)
    INPUT:   cf            - a control file object (from ConfigObj)
             <series_name> - the name of the series (string)
    RETURNS: section       - the name of the section containing an entry for <series_name> (string)
    Note that the returned section name is an empty string if there is no entry for <series_name> in
    the control file.
    '''
    section = ''
    sectionlist = ['Variables','Drivers','Fluxes','Respiration','Partition']
    if len(series)==0:
        msgtxt = ' get_cfsection: no input series specified'
        if mode!='quiet': log.info(msgtxt)
        return section
    for ThisSection in sectionlist:
        if ThisSection in cf.keys():
            if series in cf[ThisSection]: section = ThisSection
    if len(section)==0:
        msgtxt = ' get_cfsection: series '+str(series)+' not found in control file'
        if mode!='quiet': log.info(msgtxt)
    return section

def get_coverage_groups(ds,rad=None,met=None,flux=None,soil=None):
    level = str(ds.globalattributes['nc_level'])
    rad = ['Fsd','Fsu','Fld','Flu','Fn']
    met = ['Ah','Cc','Precip','ps','Ta','Ws','Wd']
    flux = ['Fm','ustar','Fh','Fe','Fc']
    soil = ['Fg','Ts','Sws']
    for ThisGroup, ThisLabel in zip([rad,met,flux,soil],['radiation','meteorology','flux','soil']):
        sum_coverage = float(0); count = float(0)
        for ThisOne in ThisGroup:
            if ThisOne in ds.series.keys():
                sum_coverage = sum_coverage + float(ds.series[ThisOne]['Attr']['coverage_'+level])
                count = count + 1
        if count!=0:
            coverage_group = sum_coverage/count
        else:
            coverage_group = 0
        ds.globalattributes['coverage_'+ThisLabel+'_'+level] = str('%d'%coverage_group)

def get_coverage_individual(ds):
    level = str(ds.globalattributes['nc_level'])
    SeriesList = ds.series.keys()
    for ThisOne in ["DateTime","DateTime_UTC"]:
        if ThisOne in SeriesList: SeriesList.remove(ThisOne)
    for ThisOne in SeriesList:
        num_good = len(numpy.where(abs(ds.series[ThisOne]['Data']-float(c.missing_value))>c.eps)[0])
        coverage = 100*float(num_good)/float(ds.globalattributes['nc_nrecs'])
        ds.series[ThisOne]['Attr']['coverage_'+level] = str('%d'%coverage)

def get_datetimefromxldate(ds):
    ''' Creates a series of Python datetime objects from the Excel date read from the Excel file.
        Thanks to John Machin for the quick and dirty code
         see http://stackoverflow.com/questions/1108428/how-do-i-read-a-date-in-excel-format-in-python'''

    log.info(' Getting the Python datetime series from the Excel datetime')
    xldate = ds.series['xlDateTime']['Data']
    nRecs = len(ds.series['xlDateTime']['Data'])
    datemode = int(ds.globalattributes['xl_datemode'])
    ds.series[unicode('DateTime')] = {}
    ds.series['DateTime']['Data'] = [None]*nRecs
    basedate = datetime.datetime(1899, 12, 30)
    for i in range(nRecs):
        ds.series['DateTime']['Data'][i] = basedate + datetime.timedelta(days=xldate[i] + 1462 * datemode)
    ds.series['DateTime']['Flag'] = numpy.zeros(nRecs)
    ds.series['DateTime']['Attr'] = {}
    ds.series['DateTime']['Attr']['long_name'] = 'Datetime in local timezone'
    ds.series['DateTime']['Attr']['units'] = 'None'

def get_datetimefromymdhms(ds):
    ''' Creates a series of Python datetime objects from the year, month,
    day, hour, minute and second series stored in the netCDF file.'''
    SeriesList = ds.series.keys()
    if 'Year' not in SeriesList or 'Month' not in SeriesList or 'Day' not in SeriesList or 'Hour' not in SeriesList or 'Minute' not in SeriesList or 'Second' not in SeriesList:
        log.info(' get_datetimefromymdhms: unable to find all datetime fields required')
        return
    log.info(' Getting the date and time series')
    nRecs = get_nrecs(ds)
    ds.series[unicode('DateTime')] = {}
    ds.series['DateTime']['Data'] = [None]*nRecs
    for i in range(nRecs):
        ds.series['DateTime']['Data'][i] = datetime.datetime(int(ds.series['Year']['Data'][i]),
                                                       int(ds.series['Month']['Data'][i]),
                                                       int(ds.series['Day']['Data'][i]),
                                                       int(ds.series['Hour']['Data'][i]),
                                                       int(ds.series['Minute']['Data'][i]),
                                                       int(ds.series['Second']['Data'][i]))
    ds.series['DateTime']['Flag'] = numpy.zeros(nRecs)
    ds.series['DateTime']['Attr'] = {}
    ds.series['DateTime']['Attr']['long_name'] = 'Date-time object'
    ds.series['DateTime']['Attr']['units'] = 'None'

def get_nrecs(ds):
    if 'nc_nrecs' in ds.globalattributes.keys():
        nRecs = int(ds.globalattributes['nc_nrecs'])
    elif 'NumRecs' in ds.globalattributes.keys():
        nRecs = int(ds.globalattributes['NumRecs'])
    else:
        nRecs = len(ds.series[SeriesList[0]]['Data'])
    return nRecs

def get_timezone(site_name):
    """ Return the time zone based on the site name."""
    tz_dict = {"adelaideriver":"Australia/Darwin",
               "alicespringsmulga":"Australia/Darwin",
               "arcturus":"Australia/Brisbane",
               "calperum":"Australia/Adelaide",
               "capetribulation":"Australia/Brisbane",
               "cumberlandplains":"Australia/Sydney",
               "cup_ec":"Australia/Sydney",
               "daintree":"Australia/Brisbane",
               "dalypasture":"Australia/Darwin",
               "dalyregrowth":"Australia/Darwin",
               "dalyuncleared":"Australia/Darwin",
               "dargo":"Australia/Melbourne",
               "dryriver":"Australia/Darwin",
               "foggdam":"Australia/Darwin",
               "gingin":"Australia/Perth",
               "greatwestern":"Australia/Perth",
               "howardsprings":"Australia/Darwin",
               "litchfield":"Australia/Darwin",
               "nimmo":"Australia/Sydney",
               "reddirt":"Australia/Darwin",
               "riggs":"Australia/Melbourne",
               "robson":"Australia/Brisbane",
               "samford":"Australia/Brisbane",
               "sturtplains":"Australia/Darwin",
               "titreeeast":"Australia/Darwin",
               "tumbarumba":"Australia/Canberra",
               "wallaby":"Australia/Melbourne",
               "warra":"Australia/Hobart",
               "whroo":"Australia/Melbourne",
               "wombat":"Australia/Melbourne",
               "yanco_jaxa":"Australia/Sydney"}
    # strip out spaces and commas from the site name
    site_name = site_name.replace(" ","").replace(",","")
    for item in tz_dict.keys():
        if item in site_name.lower():
            time_zone = tz_dict[item]
        else:
            # cant find the site in the dictionary so ask the user
            root = Tkinter.Tk(); root.withdraw()
            time_zone = tkSimpleDialog.askstring("Time zone","Enter time zone eg Australia/Melbourne")
            root.destroy()
    return time_zone

def get_UTCfromlocaltime(ds):
    '''
    PURPOSE:
     Creates a UTC datetime series in the data structure from the
     local datetime series.
    USAGE:
     qcutils.get_UTCfromlocaltime(ds)
    ASSUMPTIONS:
     No daylight savings used in the local datetime
    AUTHOR: PRI
    '''
    # check the time_zone global attribute is set, we cant continue without it
    if "time_zone" not in ds.globalattributes.keys():
        log.error("get_UTCfromlocaltime: time_zone not in global attributes")
        return
    log.info(' Getting the UTC datetime from the local datetime')
    # get the number of records
    nRecs = len(ds.series['xlDateTime']['Data'])
    # get the time zone
    tz = ds.globalattributes["time_zone"]
    # create a timezone object
    loc_tz = pytz.timezone(tz)
    # local pointer to the datetime series in ds
    ldt = ds.series["DateTime"]["Data"]
    # localise the datetime
    ldt_loc = [loc_tz.localize(dt) for dt in ldt]
    # convert to UTC
    ldt_utc = [dt.astimezone(pytz.utc) for dt in ldt_loc]
    # put the UTC datetime into the data structure
    ds.series[unicode("DateTime_UTC")] = {}
    ds.series["DateTime_UTC"]["Data"] = ldt_utc
    ds.series['DateTime_UTC']["Flag"] = numpy.zeros(nRecs)
    ds.series['DateTime_UTC']["Attr"] = {}
    ds.series['DateTime_UTC']["Attr"]["long_name"] = "Datetime as UTC"
    ds.series['DateTime_UTC']["Attr"]["units"] = "None"

def get_xldate_from_datetime(dt,datemode=0):
    '''
    PURPOSE:
     Returns a list of xldatetime (floating point number represent decimal days
     since 00:00 1/1/1900) from a list of Python datetimes
    USAGE:
    datemode = ds.globalattributes["xl_datemode"]
     xl_date = qcutils.get_xldate_from_datetime(py_date,datemode=datemode)
     ds.series["xlDateTime"] = numpy.array(xl_date)
    ASSUMPTIONS:
     datemode is set to 0 (1900 date system), use on Windows assumed
    AUTHOR: PRI
    '''
    xldate = [xlrd.xldate.xldate_from_datetime_tuple((dt[i].year,
                                                      dt[i].month,
                                                      dt[i].day,
                                                      dt[i].hour,
                                                      dt[i].minute,
                                                      dt[i].second),
                                                      datemode) for i in range(0,len(dt))]
    return xldate

def get_ymdhms_from_datetime(ds):
    '''
    PURPOSE:
     Gets the year, month, day, hour, minute and second from a list of
     Python datetimes.  The Python datetime series is read from
     the input data structure abd the results arw written back to the
     data structure.
    USAGE:
     qcutils.get_ymdhms_from_datetime(ds)
    ASSUMPTIONS:
     None
    AUTHOR: PRI
    '''
    nRecs = int(ds.globalattributes["nc_nrecs"])
    dt = ds.series["DateTime"]["Data"]
    flag = numpy.zeros(nRecs,dtype=numpy.int32)
    Year = [dt[i].year for i in range(0,nRecs)]
    Month = [dt[i].month for i in range(0,nRecs)]
    Day = [dt[i].day for i in range(0,nRecs)]
    Hour = [dt[i].hour for i in range(0,nRecs)]
    Minute = [dt[i].minute for i in range(0,nRecs)]
    Second = [dt[i].second for i in range(0,nRecs)]
    Hdh = [float(Hour[i])+float(Minute[i])/60. for i in range(0,nRecs)]
    Ddd = [(dt[i] - datetime.datetime(Year[i],1,1)).days+1+Hdh[i]/24. for i in range(0,nRecs)]
    CreateSeries(ds,'Year',Year,Flag=flag,Attr=MakeAttributeDictionary(long_name='Year',units='none'))
    CreateSeries(ds,'Month',Month,Flag=flag,Attr=MakeAttributeDictionary(long_name='Month',units='none'))
    CreateSeries(ds,'Day',Day,Flag=flag,Attr=MakeAttributeDictionary(long_name='Day',units='none'))
    CreateSeries(ds,'Hour',Hour,Flag=flag,Attr=MakeAttributeDictionary(long_name='Hour',units='none'))
    CreateSeries(ds,'Minute',Minute,Flag=flag,Attr=MakeAttributeDictionary(long_name='Minute',units='none'))
    CreateSeries(ds,'Second',Second,Flag=flag,Attr=MakeAttributeDictionary(long_name='Second',units='none'))
    CreateSeries(ds,'Hdh',Hdh,Flag=flag,Attr=MakeAttributeDictionary(long_name='Decimal hour of the day',units='none'))
    CreateSeries(ds,'Ddd',Ddd,Flag=flag,Attr=MakeAttributeDictionary(long_name='Decimal day of the year',units='none'))

def get_ymdhmsfromxldate(ds):
    """
        Gets year, month, day, hour, and if available seconds, from
        excel-formatted Timestamp
        
        Usage qcts.get_ymdhmsfromxldate(ds)
        cf: control file
        ds: data structure
        """
    log.info(' Getting date and time variables')
    # get the date mode of the original Excel datetime
    datemode = int(ds.globalattributes['xl_datemode'])
    nRecs = len(ds.series['xlDateTime']['Data'])
    Year = numpy.array([c.missing_value]*nRecs,numpy.int32)
    Month = numpy.array([c.missing_value]*nRecs,numpy.int32)
    Day = numpy.array([c.missing_value]*nRecs,numpy.int32)
    Hour = numpy.array([c.missing_value]*nRecs,numpy.int32)
    Minute = numpy.array([c.missing_value]*nRecs,numpy.int32)
    Second = numpy.array([c.missing_value]*nRecs,numpy.int32)
    Hdh = numpy.array([c.missing_value]*nRecs,numpy.float64)
    Ddd = numpy.array([c.missing_value]*nRecs,numpy.float64)
    flag = numpy.zeros(nRecs)
    for i in range(nRecs):
        DateTuple = xlrd.xldate_as_tuple(ds.series['xlDateTime']['Data'][i],datemode)
        Year[i] = int(DateTuple[0])
        Month[i] = int(DateTuple[1])
        Day[i] = int(DateTuple[2])
        Hour[i] = int(DateTuple[3])
        Minute[i] = int(DateTuple[4])
        Second[i] = int(DateTuple[5])
        Hdh[i] = float(DateTuple[3])+float(DateTuple[4])/60.
        Ddd[i] = ds.series['xlDateTime']['Data'][i] - xlrd.xldate.xldate_from_date_tuple((Year[i],1,1),datemode) + 1
    CreateSeries(ds,'Year',Year,Flag=flag,Attr=MakeAttributeDictionary(long_name='Year',units='none'))
    CreateSeries(ds,'Month',Month,Flag=flag,Attr=MakeAttributeDictionary(long_name='Month',units='none'))
    CreateSeries(ds,'Day',Day,Flag=flag,Attr=MakeAttributeDictionary(long_name='Day',units='none'))
    CreateSeries(ds,'Hour',Hour,Flag=flag,Attr=MakeAttributeDictionary(long_name='Hour',units='none'))
    CreateSeries(ds,'Minute',Minute,Flag=flag,Attr=MakeAttributeDictionary(long_name='Minute',units='none'))
    CreateSeries(ds,'Second',Second,Flag=flag,Attr=MakeAttributeDictionary(long_name='Second',units='none'))
    CreateSeries(ds,'Hdh',Hdh,Flag=flag,Attr=MakeAttributeDictionary(long_name='Decimal hour of the day',units='none'))
    CreateSeries(ds,'Ddd',Ddd,Flag=flag,Attr=MakeAttributeDictionary(long_name='Decimal day of the year',units='none'))

def haskey(cf,ThisOne,key):
    return key in cf['Variables'][ThisOne].keys()

def incf(cf,ThisOne):
    return ThisOne in cf['Variables'].keys()

def MakeAttributeDictionary(**kwargs):
    default_list = ['ancillary_variables','height','instrument','serial_number','standard_name','long_name','units']
    attr = {}
    for item in kwargs:
        attr[item] = kwargs.get(item,'not defined')
        if item in default_list: default_list.remove(item)
    if len(default_list)!=0:
        for item in default_list: attr[item] = 'not defined'
    attr["missing_value"] = c.missing_value
    return attr

def MakeQCFlag(ds,SeriesList):
    flag = []
    if len(SeriesList)<=0:
        #log.info('  MakeQCFlag: no series list specified')
        pass
    if len(SeriesList)==1:
        if SeriesList[0] in ds.series.keys():
            flag = ds.series[SeriesList[0]]['Flag'].copy()
        else:
            log.error('  MakeQCFlag: series '+str(SeriesList[0])+' not in ds.series')
    if len(SeriesList)>1:
        for ThisOne in SeriesList:
            if ThisOne in ds.series.keys():
                if len(flag)==0:
                    #flag = numpy.ones(numpy.size(ds.series[ThisOne]['Flag']))
                    flag = ds.series[ThisOne]['Flag'].copy()
                else:
                    tmp_flag = ds.series[ThisOne]['Flag'].copy()      # get a temporary copy of the flag
                    index = numpy.where(numpy.mod(tmp_flag,10)==0)    # find the elements with flag = 0, 10, 20 etc
                    tmp_flag[index] = 0                               # set them all to 0
                    flag = numpy.maximum(flag,tmp_flag)               # now take the maximum
            else:
                log.error('  MakeQCFlag: series '+ThisOne+' not in ds.series')
    return flag

def MAtoSeries(Series):
    """
    Convert a masked array to a numpy ndarray with masked elements set to c.missing_value.
    Useage:
     Series, WasMA = MAtoSeries(Series)
     where:
      Series (input)    is the data series to be converted.
      WasMA  (returned) is a logical, True if the input series was a masked array.
      Series (output)   is the input series convered to an ndarray with c.missing_value values
                        for missing data.
    """
    WasMA = False
    if numpy.ma.isMA(Series):
        WasMA = True
        Series = numpy.ma.filled(Series,float(c.missing_value))
    return Series, WasMA

def MergeQCFlag(QCFlag_list):
    """ Merge a list of QC flags by taking the element-wise maximum."""
    if len(QCFlag_list)==0: return None
    if len(QCFlag_list)==1: return QCFlag_list[0]
    flag = QCFlag_list[0].copy()                            # get a copy of the first flag
    for item in QCFlag_list[1:]:                            # loop over the list of flags
        tmp_flag = item.copy()                              # get a copy of the next flag
        index = numpy.where(numpy.mod(tmp_flag,10)==0)      # find the elements with flag = 0, 10, 20 etc
        tmp_flag[index] = 0                                 # set them all to 0
        flag = numpy.maximum(flag,tmp_flag)                 # now take the maximum
    return flag

def nxMom_nxScalar_alpha(zoL):
    nRecs = numpy.size(zoL)
    nxMom = numpy.ma.ones(nRecs) * 0.079
    nxScalar = numpy.ma.ones(nRecs) * 0.085
    alpha = numpy.ma.ones(nRecs) * 0.925
    #  get the index of stable conditions
    stable = numpy.ma.where(zoL>0)[0]
    #  now set the series to their stable values
    nxMom[stable] = 0.079 * (1 + 7.9 * zoL[stable]) ** 0.75
    nxScalar[stable] = 2.0 - 1.915 / (1 + 0.5 * zoL[stable])
    alpha[stable] = 1
    return nxMom, nxScalar, alpha

def perdelta(start, end, delta):
    """
    Yields an iterator of datetime objects from start to end with time step delta.
    """
    curr = start
    while curr < end:
        yield curr
        curr += delta

def polyval(p,x):
    """
    Replacement for the polyval routine in numpy.  This version doesnt check the
    input variables to make sure they are array_like.  This means that when
    masked arrays are treated correctly when they are passed to this routine.
    Parameters
    ----------
     p : a 1D array of coefficients, highest order first
     x : a 1D array of points at which to evaluate the polynomial described by
         the coefficents in p
    Example
    -------
    >>> x = numpy.array([1,2,3])
    >>> p = numpy.array([2,0])
    >>> qcutils.polyval(p,x)
        array([2,4,6])
    >>> y = numpy.array([1,c.missing_value,3])
    >>> y = numpy.ma.masked_where(y==c.missing_value,y)
    >>> qcutils.polyval(p,y)
    masked_array(data = [2 -- 6],
                 mask = [False True False],
                 fill_value = 999999)
    """
    y = 0
    for i in range(len(p)):
        y = x*y + p[i]
    return y

def RoundDateTime(datetimeseries,dt=30):
    RoundedDateTime = []
    for tm in datetimeseries:
        tm += datetime.timedelta(minutes=int(dt/2))
        tm -= datetime.timedelta(minutes=tm.minute % int(dt),
                                 seconds=tm.second,
                                 microseconds=tm.microsecond)
        RoundedDateTime.append(tm)
    return RoundedDateTime

def round2sig(x,sig=2):
    '''
    Round a float to a specified number of significant digits (default is 2).
    '''
    return round(x, sig-int(math.floor(math.log10(abs(x))))-1)

def r(b, p, alpha):
    """
    Function to calculate the r coeficient of the Massman frequency correction.
    """
    r = ((b ** alpha) / (b ** alpha + 1)) * \
           ((b ** alpha) / (b ** alpha + p ** alpha)) * \
           (1 / (p ** alpha + 1))
    return r

def SeriestoMA(Series):
    """
    Convert a numpy ndarray to a masked array.
    Useage:
     Series, WasND = SeriestoMA(Series)
     where:
      Series (input)    is the data series to be converted.
      WasND  (returned) is a logical, True if the input series was an ndarray
      Series (output)   is the input series convered to a masked array.
    """
    WasND = False
    if not numpy.ma.isMA(Series):
        WasND = True
        Series = numpy.ma.masked_where(abs(Series-numpy.float64(c.missing_value))<c.eps,Series)
    return Series, WasND

def SetUnitsInds(ds, ThisOne, units):
    ds.series[ThisOne]['Attr']['units'] = units

def startlog(loggername,loggerfile):
    logger = logging.getLogger(loggername)
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(loggerfile)
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%H:%M:%S')
    #formatter = logging.Formatter('%(asctime)s %(name)-8s %(levelname)-6s %(message)s', '%d-%m-%y %H:%M')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

def Wegstein(T, Ah, p, Fh, u, z, z0):

    NumIters = 50
    SolveErr = numpy.float64(0.001)
 
    FirstEst =  u*c.k/math.log(z/z0)
    ustar = Fustar(T, Ah, p, Fh, u, z, z0, FirstEst)
    Inc = ustar-FirstEst
    IncDiv = -Inc
    Residual = ustar-Fustar(T, Ah, p, Fh, u, z, z0, ustar)
 
    i = 1
    while (i<NumIters)&(float(Residual)>float(SolveErr)):
        IncDiv = (IncDiv/Residual)-1
        if (IncDiv == 0):
            print 'Wegstein: IncDiv equals 0'
            ustar = u*c.k/math.log(z/z0)
            break
        Inc = Inc/IncDiv
        ustar = ustar+Inc
        IncDiv = Residual
        Residual = ustar-Fustar(T, Ah, p, Fh, u, z, z0, ustar)
        if (abs(ustar)<=1):
            RangeErr = SolveErr
        else:
            RangeErr = SolveErr*abs(ustar)
        if (abs(Inc)<=RangeErr):
            if (abs(Residual)<=10*RangeErr):
                break
        i = i + 1
    if (i==NumIters):
        print 'Wegstein: did not converge'
        ustar = u*c.k/math.log(z/z0)
    return ustar
