/**
 # Fluid Simulation Data Extraction
 
 This program extracts and processes data from fluid dynamics simulation 
 snapshots. It calculates key fluid mechanics quantities like strain rate
 tensor invariants and velocity magnitudes from simulation output files.
 
 ## Physical Background
 
 The code analyzes the spatial derivatives of velocity fields to compute
 the second invariant of the strain rate tensor, which is an important
 quantity for identifying vortical structures in fluid flows. Additionally,
 it calculates velocity magnitudes throughout the flow field.
 
 The strain rate tensor is a fundamental quantity in fluid mechanics that 
 describes the rate of deformation of fluid elements. Its second invariant
 is particularly useful for identifying regions of strong vorticity and shear,
 making it valuable for visualizing coherent structures in turbulent flows.
 
 ## Usage
 
 ```
 ./program filename xmin ymin xmax ymax ny
 ```
 
 - filename: Path to simulation snapshot file
 - xmin, ymin: Minimum coordinates of the region of interest
 - xmax, ymax: Maximum coordinates of the region of interest
 - ny: Number of grid points in y-direction (resolution)
 
 @author Vatsal Sanjay
 @affiliation Physics of Fluids Group, University of Twente
 @email vatsalsanjay@gmail.com
 */

#include "utils.h"
#include "output.h"

scalar f[];  // Volume fraction field
vector u[];  // Velocity field

char filename[80];
int nx, ny, len;
double xmin, ymin, xmax, ymax, Deltax, Deltay;

scalar D2c[], vel[];  // Derived fields
scalar * list = NULL;  // List of fields to output

/**
 ### Main Function
 
 Processes command line arguments, restores simulation data,
 computes derived quantities, and outputs results to a formatted file.
 
 - a: Number of command line arguments
 - arguments: Array of command line argument strings
 
 Returns exit status code
 */
int main(int a, char const *arguments[])
{
  // Parse command line arguments
  sprintf(filename, "%s", arguments[1]);
  xmin = atof(arguments[2]); ymin = atof(arguments[3]);
  xmax = atof(arguments[4]); ymax = atof(arguments[5]);
  ny = atoi(arguments[6]);

  // Initialize list of fields to output
  list = list_add(list, D2c);
  list = list_add(list, vel);

  /**
   ## Data Processing
   
   Restores simulation data and calculates derived quantities at each point:
   
   - D2c: Log10 of the second invariant of the strain rate tensor
   - vel: Velocity magnitude field
   
   The strain rate tensor components are computed using finite difference
   approximations of the velocity gradients.
   */
  restore(file = filename);
  foreach() {
    // Calculate components of the strain rate tensor
    double D11 = (u.y[0, 1] - u.y[0, -1])/(2 * Delta);
    double D22 = (u.y[]/y);
    double D33 = (u.x[1, 0] - u.x[-1, 0])/(2 * Delta);
    double D13 = 0.5 * ((u.y[1, 0] - u.y[-1, 0] + u.x[0, 1] - u.x[0, -1])/(2 * Delta));
    
    // Calculate the second invariant
    double D2 = (sq(D11) + sq(D22) + sq(D33) + 2.0 * sq(D13));
    D2c[] = f[] * sqrt(D2/2.0);
    
    // Convert to log scale for better visualization
    if (D2c[] > 0.) {
      D2c[] = log(D2c[])/log(10);
    } else {
      D2c[] = -10;  // Floor value for zero or negative values
    }

    // Calculate velocity magnitude
    vel[] = f[] * sqrt(sq(u.x[]) + sq(u.y[]));
  }

  /**
   ## Data Output
   
   This section handles the output of processed data:
   
   1. Calculates the mesh dimensions based on user-specified bounds
   2. Interpolates field values onto a regular grid
   3. Writes output data to a formatted text file
   
   The output format is a space-separated values file with columns:
   x-coordinate, y-coordinate, followed by values of each field in 'list'.
   */
  FILE * fp = ferr;
  
  // Calculate grid spacing and dimensions
  Deltay = (double)((ymax - ymin)/(ny));
  nx = (int)((xmax - xmin)/Deltay);
  Deltax = (double)((xmax - xmin)/(nx));
  len = list_len(list);
  
  // Allocate memory for interpolated field values
  double ** field = (double **) matrix_new(nx, ny + 1, len * sizeof(double));
  
  // Interpolate field values onto regular grid
  for (int i = 0; i < nx; i++) {
    double x = Deltax * (i + 1./2) + xmin;
    for (int j = 0; j < ny; j++) {
      double y = Deltay * (j + 1./2) + ymin;
      int k = 0;
      for (scalar s in list) {
        field[i][len * j + k++] = interpolate(s, x, y);
      }
    }
  }

  // Write interpolated data to output file
  for (int i = 0; i < nx; i++) {
    double x = Deltax * (i + 1./2) + xmin;
    for (int j = 0; j < ny; j++) {
      double y = Deltay * (j + 1./2) + ymin;
      fprintf(fp, "%g %g", x, y);
      int k = 0;
      for (scalar s in list) {
        fprintf(fp, " %g", field[i][len * j + k++]);
      }
      fputc('\n', fp);
    }
  }
  
  // Clean up resources
  fflush(fp);
  fclose(fp);
  matrix_free(field);
}