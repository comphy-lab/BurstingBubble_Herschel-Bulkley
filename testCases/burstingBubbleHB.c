/**
 * @file burstingBubbleHB.c
 * @brief Simulation of bursting bubbles in Herschel-Bulkley media using the Basilisk framework
 * @author Vatsal Sanjay
 * @version 1.0
 * @date Dec 31, 2024
 * 
 * This code simulates the dynamics of bursting bubbles in Herschel-Bulkley media,
 * particularly focusing on the formation of Worthington jets and droplets.
 * The simulation uses a two-phase flow model with Herschel-Bulkley properties,
 * implemented using the epsilon-regularisation method.
 * 
 * Usage:
 * ./program maxLevel n OhK J Bond tmax
 * where:
 *   maxLevel: Maximum refinement level for adaptive mesh
 *   n: Power-law index
 *   OhK: k-effective Ohnesorge number for the liquid phase: $Oh_k = \frac{k}{\sqrt{\rho^nR_0^{3n-1}\gamma^{2-n}}}$
 *   J: Plasto-capillary number: $\mathcal{J} = \frac{\tau_yR_0}{\gamma}$
 *   Bond: Bond number (ratio of gravitational to surface tension forces): $Bo = \frac{\rho g R_0^2}{\gamma}$
 *   tmax: Maximum simulation time
 * 
*/

#include "axi.h"
#include "navier-stokes/centered.h"

/**
 * Simulation Parameters:
 * FILTERED: Enable density and viscosity jump smoothing
 * tsnap: Time interval between snapshots (default: 1e-2)
 * fErr: Error tolerance for volume fraction (1e-3)
 * KErr: Error tolerance for curvature calculation (1e-6)
 * VelErr: Error tolerance for velocity field (1e-3)
 * Ldomain: Domain size in characteristic lengths (8)
*/
#define FILTERED // Smear density and viscosity jumps
#include "two-phaseVP-HB.h"
#include "navier-stokes/conserving.h"
#include "tension.h"

#if !_MPI
#include "distance.h"
#endif

#define tsnap (1e-2) // 0.001 only for some cases. 
// Error tolerancs
#define fErr (1e-3)                                 // error tolerance in f1 VOF
#define KErr (1e-6)                                 // error tolerance in VoF curvature calculated using heigh function method (see adapt event)
#define VelErr (1e-3)                               // error tolerances in velocity -- Use 1e-2 for low Oh and 1e-3 to 5e-3 for high Oh/moderate to high J
#define D2Err (1e-2)                             // error tolerances in conformation inside the liquid

// Numbers!
#define Ldomain 8

// boundary conditions - outflow on the right boundary
u.n[right] = neumann(0.);
p[right] = dirichlet(0.);

int MAXlevel;
double OhK, Oha, J, Bond, tmax;
char nameOut[80], dumpFile[80], logFile[80];

int  main(int argc, char const *argv[]) {
  

  L0 = Ldomain;
  origin (-L0/2., 0.);
  
  /*
  Values taken from the terminal. Here we use some representative values. In production run, you can pass it from the command line.
  */
  MAXlevel = 10; 
  n = 0.4; 
  OhK = 0.001;
  J = 2e-1; 
  Bond = 1e-1;
  tmax = 2.5e0;
  epsilon = 1e-2;

  /*
  To get from the terminal:
  // uncomment the following lines to get the arguments from the terminal

  // // First ensure that all the variables were transferred properly from the terminal or job script.
  if (argc < 7){
    fprintf(ferr, "Lack of command line arguments. Check! Need %d more arguments\n", 7-argc);
    return 1;
  }

  MAXlevel = atoi(argv[1]);
  n = atof(argv[2]);
  OhK = atof(argv[3]);
  J = atof(argv[4]);
  Bond = atof(argv[5]);
  tmax = atof(argv[6]);

  */

  init_grid (1 << 5);
  // Create a folder named intermediate where all the simulation snapshots are stored.
  char comm[80];
  sprintf (comm, "mkdir -p intermediate");
  system(comm);
  // Name of the restart file. See writingFiles event.
  sprintf (dumpFile, "restart");
  // Name of the log file. See logWriting event.
  sprintf (logFile, "logData.dat");

/**
 * Physical Properties:
 * rho1, rho2: Density of liquid and gas phases
 * mu1, mu2: Dynamic viscosity of liquid and gas phases
 * lambda1, lambda2: Relaxation times
 * G1, G2: Elastic moduli
 * Oh: Ohnesorge number for liquid phase
 * Oha: Ohnesorge number for gas phase (= 2e-2 * Oh)
 * De: Deborah number
 * Ec: Elasto-capillary number
 * Bond: Bond number
*/
  rho1 = 1., rho2 = 1e-3;
  Oha = 2e-2 * OhK;
  mu1 = OhK, mu2 = Oha;

  tauy = J;

  f.sigma = 1.0;

  TOLERANCE=1e-4;
  CFL = 1e-1;

  run();
}

event init (t = 0) {
#if _MPI // this is for supercomputers without OpenMP support
  if (!restore (file = dumpFile)){
    fprintf(ferr, "Cannot restored from a dump file!\n");
  }
#else
  if (!restore (file = dumpFile)){
      char filename[60];
      sprintf(filename,"Bo%5.4f.dat",Bond);
      FILE * fp = fopen(filename,"rb");
        if (fp == NULL){
          fprintf(ferr, "There is no file named %s\n", filename);
          // try in folder one level up
          sprintf(filename,"../Bo%5.4f.dat",Bond);
          fp = fopen(filename,"rb");
          if (fp == NULL){
            fprintf(ferr, "There is no file named %s\n", filename);
            return 1;
          }
        }
      coord* InitialShape;
      InitialShape = input_xy(fp);
      fclose (fp);
      scalar d[];
      distance (d, InitialShape);

      while (adapt_wavelet ((scalar *){f, d}, (double[]){1e-8, 1e-8}, MAXlevel).nf);
      
    // The distance function is defined at the center of each cell, we have
    // to calculate the value of this function at each vertex. 
      vertex scalar phi[];
      foreach_vertex(){
        phi[] = -(d[] + d[-1] + d[0,-1] + d[-1,-1])/4.;
      }
      
    // We can now initialize the volume fraction of the domain. 
      fractions (phi, f);
    }
  // return 1;
#endif
}

/**
## Adaptive Mesh Refinement
*/
event adapt(i++){
  scalar KAPPA[];
  curvature(f, KAPPA);

  adapt_wavelet ((scalar *){f, u.x, u.y, D2, KAPPA},
    (double[]){fErr, VelErr, VelErr, D2Err, KErr},
    MAXlevel, MAXlevel-6);
}

/**
## Dumping snapshots
*/
event writingFiles (t = 0; t += tsnap; t <= tmax) {
  dump (file = dumpFile);
  sprintf (nameOut, "intermediate/snapshot-%5.4f", t);
  dump(file=nameOut);
}

/**
## Ending Simulation
*/
event end (t = end) {
  if (pid() == 0)
    fprintf(ferr, "Level %d, n %2.1e, OhK %2.1e, Oha %2.1e, J %4.3f, Bo %4.3f\n", MAXlevel, n, OhK, Oha, J, Bond);
}

/**
## Log writing
*/
event logWriting (i++) {
  // if (i > 5){
  // FILE * ftest = fopen("test.txt", "w");
  // output_facets(f, ftest);
  // return 1;}

  double ke = 0.;
  foreach (reduction(+:ke)){
    ke += (2*pi*y)*(0.5*rho(f[])*(sq(u.x[]) + sq(u.y[])))*sq(Delta);
  }
  if (pid() == 0) {
    static FILE * fp;
    if (i == 0) {
      fprintf(ferr, "Level %d, n %2.1e, OhK %2.1e, Oha %2.1e, J %4.3f, Bo %4.3f\n", MAXlevel, n, OhK, Oha, J, Bond);
      fprintf (ferr, "i dt t ke\n");
      fp = fopen (logFile, "w");
      fprintf(fp, "Level %d, n %2.1e, OhK %2.1e, Oha %2.1e, J %4.3f, Bo %4.3f\n", MAXlevel, n, OhK, Oha, J, Bond);
      fprintf (fp, "i dt t ke\n");
      fprintf (fp, "%d %g %g %g\n", i, dt, t, ke);
      fclose(fp);
    } else {
      fp = fopen (logFile, "a");
      fprintf (fp, "%d %g %g %g\n", i, dt, t, ke);
      fclose(fp);
    }
    fprintf (ferr, "%d %g %g %g\n", i, dt, t, ke);

  assert(ke > -1e-10);

  if (ke > 1e2 && i > 1e1){
    if (pid() == 0){
      fprintf(ferr, "The kinetic energy blew up. Stopping simulation\n");
      fp = fopen (logFile, "a");
      fprintf(fp, "The kinetic energy blew up. Stopping simulation\n");
      fclose(fp);
      dump(file=dumpFile);
      return 1;
    }
  }
  assert(ke < 1e2);
  
  if (ke < 1e-6 && i > 1e1){
    if (pid() == 0){
      fprintf(ferr, "kinetic energy too small now! Stopping!\n");
      dump(file=dumpFile);
      fp = fopen (logFile, "a");
      fprintf(fp, "kinetic energy too small now! Stopping!\n");
      fclose(fp);
      return 1;
    }
  }
  }
}
