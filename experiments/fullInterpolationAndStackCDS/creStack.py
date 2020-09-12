#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# creStack  (Python)
#
# Purpose: Recipe to the cre model, interpolation and Stacking.
# 
# Important!: It should be called from a SConstruct 
#
# Site: http://www.dirackslounge.online
# 
# Version 1.0
#
# Programer: Rodolfo A. C. Neves (Dirack) 04/03/2020
#
# Email: rodolfo_profissional@hotmail.com
#
# License: GPL-3.0 <https://www.gnu.org/licenses/gpl-3.0.txt>.

# Madagascar package
from rsf.proj import *

def kirchoffModeling(filename='dataCube'):
    '''
    Modeling function of a gaussian reflector
    '''

    # Modeling: Gaussian reflector in a velocity linear model
    # velocity increases with depth with a 0.5 velocity gradient
    Flow('gaussianReflector',None,
         '''
         math d1=0.01 n1=2001 o1=-5 unit1=km label1=Offset
         output="4-3*exp(-(x1-5)^2/9)"
         ''')

    # Velocity Model
    Flow('velocityModel','gaussianReflector',
         '''
         window min1=0 max1=10 |
         spray axis=1 n=451 d=0.01 o=0 label=Depth unit=km |
         math output="1.5+0.5*x1+0.0*x2"
         ''')

    Flow('reflectorDip','gaussianReflector','math output="2/3*(x1-5)*input" ')

    # Kirchoff Modeling
    Flow(filename,'gaussianReflector reflectorDip',
         '''
         kirmod cmp=y dip=${SOURCES[1]} 
         nh=161 dh=0.025 h0=0
         ns=401 ds=0.025 s0=0
         freq=10 dt=0.004 nt=1001
         vel=1.5 gradz=0.5 gradx=0.0 verb=y |
         put d2=0.0125 label3="CMP" unit3="Km" label2="Offset" unit2="Km" label1=Time unit1=s
         ''')

def pefInterpolation(
    dataCube,
    interpolated,
    nm,
    dm,
    nt,
    dt,
    nhi=1
    ):
    '''
    PEF interpolation of the data cube
    :param dataCube: filename, Seismic data cube to interpolate
    :param interpolated: filename, Interpolated seismic data cube
    :param nm: integer, number of CMPs in the seismic data cube
    :param dm: float, CMP sampling
    :param nt: integer, number of time samples
    :param dt: float, time sampling
    :param nhi: integer, number of constant offsets gathers to interpolate
    '''

    # Divide CMP sampling
    dm = dm/2

    # Define mask file names using input filename
    mask1 = dataCube+'-mask1'
    mask = dataCube+'-mask'
    aa = dataCube+'-aa'
    bb = dataCube+'-bb'
    a = dataCube+'-a'
    b = dataCube+'-b'
    zeroTraceGather = dataCube+'-zeroedGather'
    mask0 = dataCube+'-mask0'


    # Build a mask to interleave zero traces with original data traces
    Flow(aa,None,'spike n1=%i d1=%g o1=0' %(nm,dm))
    Flow(bb,None,'spike n1=%i d1=%g o1=0 mag=0' % (nm,dm))
    Flow(mask1,[bb, aa],
            '''
            interleave axis=1 ${SOURCES[1]} |
            dd type=int
            ''')

    Flow(a,None,'spike n1=%i d1=%g o1=0' % (nm,dm))
    Flow(b,None,'spike n1=%i d1=%g o1=0 mag=0' % (nm,dm))
    Flow(mask,[a, b],
            '''
            interleave axis=1 ${SOURCES[1]} |
            dd type=int
            ''')
    Flow(zeroTraceGather,b,
            '''
            spray axis=2 n=%i d=%g |
            transp |
            put label2=Offset unit2=Km label1=Time unit1=s
            ''' %(nt,dm))

    # Data Mask with double of traces in CMP (half of CMP sampling)
    # Keep the same Time and Offset original data sampling
    Flow(mask0,mask,
         '''
         spray axis=1 n=%i d=%g
         ''' %(nt,dt))

    totalPefIterations = 100
    totalInterpolationIterations = 20

    offsetGathers = []
    for offsetGatherIndex in range(nhi):

            offsetGather = dataCube+"-offsetGather-%i" % offsetGatherIndex
            resampledOffsetGather = dataCube+"-resampledGather-%i" % offsetGatherIndex
            interpolatedOffsetGather = dataCube+"-interpolatedGather-%i" % offsetGatherIndex
            pefCoeficients = dataCube+"-pefCoeficients-%i" % offsetGatherIndex

            Flow(offsetGather,dataCube,
            '''
            window n2=1 f2=%i
            ''' % (offsetGatherIndex))
            
            Flow(resampledOffsetGather,[offsetGather,zeroTraceGather],
            '''
            interleave axis=2 ${SOURCES[1]}
            ''')

            # Calculate adaptive PEF coeficients
            Flow(pefCoeficients,[resampledOffsetGather,mask0],
                    '''
                    apef jump=2 a=10,2 rect1=50 rect2=2 niter=%g verb=y
                    maskin=${SOURCES[1]}
                    ''' % (totalPefIterations))

            # Interpolation
            Flow(interpolatedOffsetGather, 	[resampledOffsetGather,pefCoeficients,mask0,mask1],
                    '''
                    miss4 exact=y filt=${SOURCES[1]} mask=${SOURCES[2]} niter=%g verb=y |
                    put d2=%g
                    ''' % (totalInterpolationIterations,dm))

            offsetGathers.append(interpolatedOffsetGather)

    # Concatenate interpolated sections
    Flow(interpolated,offsetGathers,
            '''
            rcat axis=3 ${SOURCES[1:%d]} |
            transp plane=23
            ''' % nhi)

