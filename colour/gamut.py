#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gamut: Colour metric functions. Part of the colour package.

Copyright (C) 2013-2016 Ivar Farup, Lars Niebuhr,
Sahand Lahafdoozian, Nawar Behenam, Jakob Voigt

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as np
from scipy import spatial
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import art3d
import scipy as sci


class Gamut:
    """Class for representing colour gamuts computed in various colour spaces.
    """
    def __init__(self, sp, points, gamma=1, center=0):
        """Construct new gamut instance and compute the gamut. To initialize the hull with the convex hull method,
        set gamma != 1, and provide the center for expansion.

        :param sp : colour.Space
            The colour space for computing the gamut.
        :param points : colour.Data
            The colour points for the gamut.
        """

        self.data = points       # The data points are stored in the original format. Use hull.points for actual points.
        self.space = sp
        self.hull = None         # Initialized by initialize_(modified)convex_hull
        self.vertices = None     # Initialized by initialize_(modified)convex_hull
        self.simplices = None    # Initialized by initialize_(modified)convex_hull
        self.neighbors = None    # Initialized by initialize_(modified)convex_hull
        self.center = None       # Initialized by initialize_(modified)convex_hull

        if gamma == 1:
            self.initialize_convex_hull()
        else:
            self.initialize_modified_convex_hull(gamma, center)
        self.fix_orientation()

    def initialize_convex_hull(self):
        """Initializes the gamuts convex hull in the desired colour space

        :param sp : Space
            The colour space for computing the gamut.
        :param points : Data
            The colour points for the gamut.
        """
        # Calculate the convex hull
        self.hull = spatial.ConvexHull(self.data.get_linear(self.space), qhull_options='QJ')
        self.vertices = self.hull.vertices
        self.simplices = self.hull.simplices
        self.neighbors = self.hull.neighbors
        self.center = self.center_of_mass(self.get_coordinates(self.vertices))

    def initialize_modified_convex_hull(self, gamma, center):
        """Initializes the gamut with the modified convex hull method.

        :param gamma: float
            The exponent for modifying the radius.
        :param center: ndarray
            Center of expansion.
        """
        # Move all points so that 'center' is origin
        n_data = self.data.get(self.space)

        i = 0
        for point in n_data:
            point -= center                             # Adjust all points, so center is origin
            r = np.linalg.norm(point)                   # Get the points radius.
            n_data[i] = point * (r ** gamma / r)        # Modify their radius
            i += 1

        # Calculate the convex hull, with the modified radius's
        self.hull = spatial.ConvexHull(n_data)
        self.vertices = self.hull.vertices
        self.simplices = self.hull.simplices
        self.neighbors = self.hull.neighbors
        self.center = center

    def is_inside(self, sp, c_data):
        """For the given data points checks if points are inn the convex hull

        :param sp : colour.Space
            The colour space for computing the gamut.
        :param c_data : colour.Data
            Data object with the colour points for the gamut.
        :return ndarray
            A array shape(c_data.get()-1) which contains True for each point included in the convexHull, else False.
        """

        nd_data = c_data.get(sp)                                    # Get the data points as ndarray

        if nd_data.ndim == 1:                                       # If only one point was sent.
            return np.array([self.feito_torres(nd_data)])    # Returns 1d boolean-array

        else:
            indices = np.ones(nd_data.ndim - 1, int) * -1  # Important that indices is initialized with negative numb.
            bool_array = np.zeros(np.shape(nd_data)[:-1], bool)      # Create a bool-array with the same shape as the
            self.traverse_ndarray(nd_data, indices, bool_array)      # nd_data(minus the last dimension)

            return bool_array                                        # Returns the boolean array

    def traverse_ndarray(self, nda, indices, bool_array):
        """For the given data points checks if points are inn the convexhull

        :param nda : ndarray
            An n-dimensional array containing the remaining dimensions to iterate.
        :param indices : array
            The dimensional path to the coordinate.
            Needs to be as long as the (amount of dimensions)-1 in nda and filled with -1's
        :param bool_array : ndarray
            Array shape(nda-1) containing true/false in last dimension.
        """
        if np.ndim(nda) != 1:                               # Not yet reached a leaf node
            curr_dim = 0
            for index in np.nditer(indices):                # calculate the dimension number witch we are currently in
                if index != -1:                             # If a dimension is previously iterated the cell will
                    curr_dim += 1                           # have been changed to a non-negative number.

            numb_of_iterations = 0
            for nda_minus_one in nda:                       # Iterate over the length of the current dimension
                indices[curr_dim] = numb_of_iterations      # Update the path in indices before next recursive call
                self.traverse_ndarray(nda_minus_one, indices, bool_array)
                numb_of_iterations += 1
            indices[curr_dim] = -1                          # should reset the indices array when the call dies

        else:                                               # We have reached a leaf node
            bool_array[(tuple(indices))] = self.feito_torres(nda)  # Set the boolean array to returned boolean.

    def feito_torres(self, P):
        """ Tests if a point P is inside a convexHull(polyhedron)

        :param P: ndarray
            Point to be tested for inclusion.
        :return: bool
            True if P is included in the convexHull(polyhedron)
        """
        inclusion = 0   # Will be greater than 0 if P is inside.
        v_plus = []     # a list of vertices who's original edge contains P, and it's face is POSITIVE oriented
        v_minus = []    # a list of vertices who's original edge contains P, and it's face is NEGATIVE oriented
        origin = np.array([0., 0., 0.])

        for el in self.simplices:
            facet = self.get_coordinates(el)    # Get the coordinates for the current facet
            if self.interior(facet, P, True):      # Check if P is on the current facet.
                return True

            o_v1 = np.array([origin, facet[0]])   # Line from origo to the first vertex in the facet.
            o_vn = np.array([origin, facet[-1]])  # Line from origo to the last vertex in the facet.
            o_face = np.array([origin, facet[0], facet[1], facet[2]])  # original tetrahedra from face to origo.
            sign_face = self.sign(o_face)         # Sign of the current original tetrahedron

            # Check if P is on the original edge of the facets first vertex.
            if(self.interior(o_v1, P)) and \
                    ((sign_face > 0 and not (np.in1d(el[0], v_plus))) or  # and that the vertex is not already
                        (sign_face < 0 and not (np.in1d(el[0], v_minus)))):  # in v_plus/minus
                inclusion += sign_face

                if sign_face < 0:               # add vertex to neg. oriented facets or pos. oriented facets
                    v_minus.append(el[0])
                else:
                    v_plus.append(el[0])

            # Check if P is on the original edge of the facets last vertex.
            if(self.interior(o_vn, P)) and \
                    ((sign_face > 0 and not (np.in1d(el[-1], v_plus))) or  # and that the vertex is not already
                        (sign_face < 0 and not (np.in1d(el[-1], v_minus)))):  # in v_plus/minus
                inclusion += sign_face

                if sign_face < 0:           # add vertex to neg. oriented facets or pos. oriented facets
                    v_minus.append(el[-1])
                else:
                    v_plus.append(el[-1])

            j = 1
            for vertex in facet[1:-1]:  # For the remaining vertices
                tetra = np.array([[0., 0., 0.], facet[0], facet[j], facet[j+1]])  # original tetrahedron
                sign_tetra = self.sign(tetra)  # The sign of the original tetrahedron

                # See if P is on any of the facets original triangles.
                if self.interior(np.array([origin, facet[0], facet[j]]), P, True) or \
                    self.interior(np.array([origin, facet[j], facet[j+1]]), P, True) or \
                        self.interior(np.array([origin, facet[j+1], facet[0]]), P, True):
                    inclusion += 0.5*sign_tetra

                # See if P is the original edge of vertex j
                elif self.interior(np.array([origin, facet[j]]), P) and \
                        ((sign_tetra > 0 and not (np.in1d(vertex[j], v_plus))) or
                            (sign_tetra < 0 and not (np.in1d(vertex[j], v_minus)))):
                    inclusion += sign_tetra

                    if sign_tetra < 0:  # add vertex to neg. oriented facets or pos. oriented facets
                        v_minus.append(vertex[j])
                    else:
                        v_plus.append(vertex[j])

                # See if P is in the original tetrahedron of the current facet.
                elif self.interior(tetra, P, True):
                    inclusion += sign_tetra

                j += 1

        if inclusion > 0:
            return True
        else:
            return False

    def fix_orientation(self):
        """Fixes the orientation of the facets in the hull.
        """

        c = self.center_of_mass(self.get_coordinates(self.vertices))

        for simplex in self.simplices:
            facet = self.get_coordinates(simplex)
            normal = np.cross((facet[1] - facet[0]), facet[2] - facet[0])  # Calculate the facets normal vector
            if np.dot((facet[0]-c), normal) < 0:  # If the dot product of 'normal' and a vector from the
                                                            # center of the gamut to the facet is negative, the
                                                            # orientation of the facet needs to be fixed.
                a = simplex[2]
                simplex[2] = simplex[0]
                simplex[0] = a

    @staticmethod
    def sign(t):
        """ Calculates the orientation of the tetrahedron.

        :param t: ndarray
            shape(4,3) The four coordinates of the tetrahedron who's signed volume is to be calculated
        :return: int
             1 if tetrahedron is POSITIVE orientated(signed volume > 0)
             0 if volume is 0
            -1 if tetrahedron is NEGATIVE orientated(signed volume < 0)
        """

        matrix = np.array([  # Creating the matrix for calculating a determinant, representing
                           [t[0, 0], t[1, 0], t[2, 0], t[3, 0]],  # the signed volume of the t.
                           [t[0, 1], t[1, 1], t[2, 1], t[3, 1]],
                           [t[0, 2], t[1, 2], t[2, 2], t[3, 2]],
                           [1, 1, 1, 1]])
        return int(np.sign(sci.linalg.det(matrix)))*-1  # Calculates the signed volume and returns its sign.

        # Above code works as it should, but there must be a way to do this without multiplying with '-1'
        # The below code SHOULD WORK, but.. it doesn't.
        # matrix = np.array([[t[0, 0], t[0, 1], t[0, 2], 1],
        #                    [t[1, 0], t[1, 1], t[1, 2], 1],
        #                    [t[2, 0], t[2, 1], t[2, 2], 1],
        #                    [t[3, 0], t[3, 1], t[3, 2], 1]])
        #
        # return int(np.sign(sci.linalg.det(matrix)))

    def get_coordinates(self, indices):
        """Return the coordinates of the points correlating to the the indices provided.

        :param indices: ndarray
            shape(N,), list of indices
        :return: ndarray
            shape(N, 3)
        """
        coordinates = np.ndarray(shape=(indices.shape[0], 3))

        counter = 0
        for index in indices:
            coordinates[counter] = self.hull.points[index]  # Get the coordinates.
            counter += 1

        return coordinates

    def in_tetrahedron(self, t, p, true_interior=False):
        """Checks if the point P, pointed to by vector p, is inside(including the surface) the tetrahedron
            If 'p' is not guaranteed a true tetrahedron, use interior().

        :param t: ndarray
            The four points of a tetrahedron
        :param p: ndarray
            The point to be tested for inclusion in the tetrahedron.
        :param true_interior: bool
            Activate to exclude the surface of the tetrahedron from the search.
        :return: Bool
            True if q is inside or on the surface of the tetrahedron.
        """

        # If the surface is to be excluded, return False if p is on the surface.
        if true_interior and (self.in_triangle(np.delete(t, 0, 0), p) or
                              self.in_triangle(np.delete(t, 1, 0), p) or
                              self.in_triangle(np.delete(t, 2, 0), p) or
                              self.in_triangle(np.delete(t, 3, 0), p)):
            return False

        # Check if 'p' is in the tetrahedron.
        hull = spatial.Delaunay(t)    # Generate a convexHull representation of the points
        return hull.find_simplex(p) >= 0        # return True if 'p' is a vertex.

    def in_line(self, line, point, true_interior=False):
        """Checks if a point P is on the line segment AB.

        :param line: ndarray
            line segment from point A to point B
        :param point: ndarray
            Vector from A to P
        :return: Bool
        :param true_interior: bool
            Set to True if you want to exclude the end points in the search for inclusion.
        :return: Bool
            True is P in in the line segment from A to P.
        """
        if true_interior and (tuple(point) == tuple(line[0]) or tuple(point) == tuple(line[1])):  #
            return False

        b = line[1] - line[0]   # Move the line so that A is (0,0,0). 'b' is the vector from A to B.
        p = point - line[0]     # Make the same adjustments to the points. Copy to not change the original point

        # Check if the cross b x p is 0, if not the vectors are not collinear.
        matrix = np.array([[1, 1, 1], b, p, ])
        if np.linalg.det(matrix) != 0:
            return False

        # Check if b and p have opposite directions
        dot_b_p = np.dot(p, b)
        if dot_b_p < 0:
            return False

        # Finally check that p-vector is than shorter b-vector
        if np.linalg.norm(p) > np.linalg.norm(b):
            return False

        return True

    def in_triangle(self, triangle, P, true_interior=False):
        """Takes three points of a triangle in 3d, and determines if the point w is within that triangle.
            This function utilizes the baycentric technique explained here
            https://blogs.msdn.microsoft.com/rezanour/2011/08/07/barycentric-coordinates-and-point-in-triangle-tests/

        :param triangle: ndarray
            An ndarray with shape: (3,3), with points A, C and C being triangle[0]..[2]
        :param P: ndarray
            An ndarray with shape: (3,), the point to be tested for inclusion in the triangle.
        :param true_interior: bool
            If true_interior is set to True, returns False if 'P' is on one of the triangles edges.

        :return: bool
            True if 'w' is within the triangle ABC.
        """

        # If the true interior option is activated, return False if 'P' is on one of the triangles edges.
        if true_interior and (self.in_line(triangle[0:2], P) or
                              self.in_line(triangle[1:3], P) or
                              self.in_line(np.array([triangle[0], triangle[2]]), P)):
            return False

        # Make 'A' the local origin for the points.
        b = triangle[1] - triangle[0]  # 'b' is the vector from A to B
        c = triangle[2] - triangle[0]  # 'c' is the vector from A to C
        p = P - triangle[0]            # 'p' is now the vector from A to the point being tested for inclusion

        # If triangle is actually a line. It is treated as a line.
        if np.array_equal(triangle[0], triangle[1]):
            return self.in_line(np.array([triangle[0], triangle[1]]), p)
        if np.array_equal(triangle[0], triangle[2]):
            return self.in_line(np.array([triangle[0], triangle[2]]), p)
        if np.array_equal(triangle[1], triangle[2]):
            return self.in_line(np.array([triangle[1], triangle[2]]), p)

        b_x_c = np.cross(b, c)         # Calculating the vector of the cross product b x c
        if np.dot(b_x_c, p) != 0:      # If p-vector is not coplanar to b and c-vector, it is not in the triangle.
            return False

        c_x_p = np.asarray(np.cross(c, p))          # Calculating the vector of the cross product c x p
        c_x_b = np.asarray(np.cross(c, b))          # Calculating the vector of the cross product c x b

        if np.dot(c_x_p, c_x_b) < 0:    # If the two cross product vectors are not pointing in the same direction. exit
            return False

        b_x_p = np.asarray(np.cross(b, p))          # Calculating the vector of the cross product b x p

        if np.dot(b_x_p, b_x_c) < 0:  # If the two cross product vectors are not pointing in the same direction. exit
            return False

        denom = np.linalg.norm(b_x_c)
        r = np.linalg.norm(c_x_p) / denom
        t = np.linalg.norm(b_x_p) / denom

        return r + t <= 1

    @staticmethod
    def is_coplanar(p):
        """Checks if the points provided are coplanar. Does not handle more than 4 points.

        :param p: ndarray
            The points to be tested
        :return: bool
            True if the points are coplanar
        """
        if p.shape[0] < 4:  # Less than 4 p guarantees coplanar p.
            return True

        # Make p[0] the local origin, and d, c, and d vectors from origin to the other points.
        b = p[1] - p[0]
        c = p[2] - p[0]
        d = p[3] - p[0]

        return np.dot(d, np.cross(b, c)) == 0   # Coplanar if the cross product vector or two vectors dotted with the
                                                # last vector is 0.

    @staticmethod
    def center_of_mass(points):
        """Finds the center of mass of the points given. To find the "geometric center" of a gamut
        lets points be only the vertices of the gamut.

        Thanks to: http://stackoverflow.com/questions/8917478/center-of-mass-of-a-numpy-array-how-to-make-less-verbose

        :param points: ndarray
            Shape(N, 3), a list of points
        :return: center: ndarray
            Shape(3,), the coordinate of the center of mass.
        """
        cm = points.sum(0) / points.shape[0]
        for i in range(points.shape[0]):
            points[i, :] -= cm
        return cm

    def get_vertices(self, nd_data):
        """Get all hull vertices and save them in a array list.

        :param nd_data : ndarray
            Shape(N, 3) A list of points to return vertices from. The a copy of gamut.points pre-converted
            to a desired colour space.
        :return: ndarray
            The coordinates of the requested vertices
        """
        point_list = []                     # Array list for the vertices.

        for i in self.hull.vertices:        # For loop that goes through all the vertices
            point_list.append(nd_data[i])   # and for each goes to the points and adds the coordinents to the list.

        return np.array(point_list)          # Returns ndarray.

    def plot_surface(self, ax, sp):
        """Plot all the vertices points on the received axel

        :param ax: Axel
            The axel to draw the points on
        :param sp: Space
            The colour space for computing the gamut.
        """
        nd_data = self.data.get_linear(sp)              # Creates a new ndarray with points
        points = self.get_vertices(nd_data)             # ndarray with all the vertices
        x = points[:, 0]
        y = points[:, 1]
        z = points[:, 2]

        for i in range(self.hull.simplices.shape[0]):   # Iterates and draws all the vertices points
            tri = art3d.Poly3DCollection([self.hull.points[self.hull.simplices[i]]])
            ax.add_collection(tri)                      # Adds created points to the ax

        ax.set_xlim([0, 10])                            # Set the limits for the plot manually
        ax.set_ylim([-10, 10])
        ax.set_zlim([-10, 10])
        plt.show()

    def true_shape(self, points):
        """Removes all points in 'points' the does not belong to it's convex polygon.
            Works with 4 or less coplanar points.
        :param points: ndarray
            Shape(N, 3) Points in 3d
        :return: ndarray
            The vertices of a assuming it is supposed to represent a convex shape
        """

        # Remove duplicate points.
        uniques = []  # Use list while removing
        for arr in points:
            if not any(np.array_equal(arr, unique_arr) for unique_arr in uniques):
                uniques.append(arr)
        uniques = np.array(uniques)  # Convert back to ndarray.

        if uniques.shape[0] < 3:  # one or two unique points are garaunteed a point or line.
            return uniques

        # If we have 3 points, they are either a triangle or a line.
        if uniques.shape[0] == 3:
            i = 0
            while i < 3:
                a = np.delete(uniques, i, 0)
                if self.in_line(a, uniques[i]):  # If a point is on the line segment between two other points
                    return a           # Return that line segment.
                i += 1
            return uniques  # Guaranteed to be a triangle.

        i = 0
        while i < 4:
            b = np.delete(uniques, i, 0)
            if self.in_triangle(b, uniques[i]):  # See if any of the points lay inside the triangle formed by the
                return b                         # other points
            i += 1

        return uniques  # return a convex polygon with 4 vertices

    def interior(self, pts, q, true_interior=False):
        """ Finds the vertecis of pts's convex shape, and calls the appropriate function
            to test for inclusion
            Is not designed to work with more than 4 points.
        :param pts: ndarray
            Shape(n, 3). 0 < n < 5.
        :param q:
            Point to be tested for inclusion in pts's true shape.
        :param true_interior:
            Activate to exclude the edges if pts is acctually a triangle or polygon with 4 vertecis, or the surface
             if pts is a tetrahedron
        :return:
        """
        if self.is_coplanar(pts):
            true_shape = self.true_shape(pts)
            if true_shape.shape[0] == 1:
                return np.allclose(true_shape, q)
            elif true_shape.shape[0] == 2:
                return self.in_line(true_shape, q)
            elif true_shape.shape[0] == 3:
                return self.in_triangle(true_shape, q, true_interior=true_interior)
            elif true_shape.shape[0] == 4:
                return self.in_polygon(true_shape, q, true_interior=true_interior)
            else:
                print("Error: interior received to many points, retuning False")
                return False
        else:
            return self.in_tetrahedron(pts, q, true_interior=true_interior)

    def in_polygon(self, pts, q, true_interior=False):
        """Checks if q is in the polygon formed by pts

        :param pts: ndarray
            shape(4, 3). Points on a polygon. Must be coplanar.
        :param q: ndarray
            Point to be tested for inclusion
        :param true_interior: boolean
            Activate to exclude the edges from the search
        :return:
        """
        if true_interior:
            # Divide into two triangles and check their true_interior, and their common edge with is in the true
            # interior or the polygon
            return (self.in_triangle(np.array([pts[0], pts[1], pts[2]]), q, true_interior=True) or
                    self.in_line(np.array([pts[1], pts[2]]), q, true_interior=True) or
                    self.in_triangle(np.array([pts[1], pts[2], pts[3]]), q, true_interior=True))
        else:
            # Divide in two triangles and see is q is in either.
            return (self.in_triangle(np.array([pts[0], pts[1], pts[2]]), q) or
                    self.in_triangle(np.array([pts[1], pts[2], pts[3]]), q))

    @staticmethod
    def is_coplanar(p):
        """Checks if the points provided are coplanar. Does not handle more than 4 points.

        :param points: ndarray
            The points to be tested
        :return: bool
            True if the points are coplanar
        """
        if p.shape[0] < 4:  # Less than 4 p guarantees coplanar p.
            return True

        # Make p[0] the local origin, and d, c, and d vectors from origo to the other points.
        b = p[1] - p[0]
        c = p[2] - p[0]
        d = p[3] - p[0]

        return np.dot(d, np.cross(b, c)) == 0  # Coplanar if the cross product vector or two vectors dotted with the
        #  last vector is 0.

    @staticmethod
    def center_of_mass(points):
        """Finds the center of mass of the points given. To find the "geometric center" of a gamut
        lets points be only the vertices of the gamut.

        Thanks to: http://stackoverflow.com/questions/8917478/center-of-mass-of-a-numpy-array-how-to-make-less-verbose

        :param points: ndarray
            Shape(N, 3), a list of points
        :return: center: ndarray
            Shape(3,), the coordinate of the center of mass.
        """
        cm = points.sum(0) / points.shape[0]
        for i in range(points.shape[0]):
            points[i, :] -= cm
        return cm

    def true_shape(self, points):
        """Removes all points in 'points' the does not belong to it's convex polygon.
            Works with 4 or less coplanar points.
        :param points: ndarray
            Shape(N, 3) Points in 3d
        :return: ndarray
            The vertices of a assuming it is supposed to represent a convex shape
        """

        # Remove duplicate points.
        uniques = []  # Use list while removing
        for arr in points:
            if not any(np.array_equal(arr, unique_arr) for unique_arr in uniques):
                uniques.append(arr)
        uniques = np.array(uniques)  # Convert back to ndarray.

        if uniques.shape[0] < 3:  # one or two unique points are garaunteed a point or line.
            return uniques

        # If we have 3 points, they are either a triangle or a line.
        if uniques.shape[0] == 3:
            i = 0
            while i < 3:
                a = np.delete(uniques, i, 0)
                if self.in_line(a, uniques[i]):  # If a point is on the line segment between two other points
                    return a           # Return that line segment.
                i += 1
            return uniques  # Guaranteed to be a trinalge.

        i = 0
        while i < 4:
            b = np.delete(uniques, i, 0)
            if self.in_triangle(b, uniques[i]):  # See if any of the points lay inside the triangle formed by the
                return b                         # other points
            i += 1

        return uniques  # return a convex polygon with 4 vertices

    def interior(self, pts, q, true_interior=False):
        """ Finds the vertices of pts convex shape, and calls the appropriate function
            to test for inclusion.
            Is not designed to work with more than 4 points.
        :param pts: ndarray
            Shape(n, 3). 0 < n < 5.
        :param q: ndarray
            Point to be tested for inclusion in pts true shape.
        :param true_interior: boolean
            Activate to exclude the edges if pts is actually a triangle or polygon with 4 vertices, or the surface
            if pts is a tetrahedron
        :return: boolean
            True if the point was inside.
        """
        if self.is_coplanar(pts):
            true_shape = self.true_shape(pts)
            if true_shape.shape[0] == 1:
                return np.allclose(true_shape, q)
            elif true_shape.shape[0] == 2:
                return self.in_line(true_shape, q)
            elif true_shape.shape[0] == 3:
                return self.in_triangle(true_shape, q, true_interior=true_interior)
            elif true_shape.shape[0] == 4:
                return self.in_polygon(true_shape, q, true_interior=true_interior)
            else:
                print("Error: interior received to many points, retuning False")
                return False
        else:
            return self.in_tetrahedron(pts, q, true_interior=true_interior)

    def in_polygon(self, pts, q, true_interior=False):
        """Checks if q is in the polygon formed by pts

        :param pts: ndarray
            shape(4, 3). Points on a polygon. Must be coplanar.
        :param q: ndarray
            Point to be tested for inclusion
        :param true_interior: boolean
            Activate to exclude the edges from the search
        :return:
        """
        if true_interior:
            # Divide into two triangles and check their true_interior, and their common edge with is in the true
            # interior or the polygon
            return (self.in_triangle(np.array([pts[0], pts[1], pts[2]]), q, true_interior=True) or
                    self.in_line(np.array([pts[1], pts[2]]), q, true_interior=True) or
                    self.in_triangle(np.array([pts[1], pts[2], pts[3]]), q, true_interior=True))
        else:
            # Divide in two triangles and see is q is in either.
            return (self.in_triangle(np.array([pts[0], pts[1], pts[2]]), q) or
                    self.in_triangle(np.array([pts[1], pts[2], pts[3]]), q))

    def get_alpha(self, d, center, n):
        """Get the Alpha value by computing.

        :param d: ndarray
            The start point.
        :param center: ndarray
            The center is a end point in the color space.
        :param n: ndarray
            The normal and distance value for the simplex
        :return x: float
            Returns alpha value.
        """
        x = (n[3] - center[0] * n[0] - center[1] * n[1] - center[2] * n[2]) / \
            (d[0] * n[0] - center[0] * n[0] + d[1] * n[1] - center[1] * n[1] + d[2] * n[2] - center[2] * n[2])

        return x

    def find_plane(self, points):
        """Find normal point to a plane(simplices) and the distance from p to the cross point.

        :param points: ndarray
            the start point.
        :return n: ndarray
            Returns ndarray with normal points distance. [x, y, z, distance]
        """

        v1 = points[2] - points[0]
        v2 = points[1] - points[0]
        n2 = np.cross(v1, v2)                          # Find cross product of 2 points.
        nnorm = np.linalg.norm(n2)                     # Find normal point.
        n3 = n2 / nnorm                                # Find the distance.
        n = np.hstack([n3, np.dot(points[1], n3)])     # Add the distance to numpy array.

        return n

    def intersectionpoint_on_line(self, d, center, sp):
        """Finding the Nearest point along a line.

        :param d: ndarray
            The start point.
        :param center: ndarray
            The center is a end point in the color space.
        :param sp: Space
            The colour space for computing the gamut.
        :return: ndarray
            Return the nearest point.
        """
        new_points = self.data.get(sp)                 # Converts gamut to new space
        alpha = []                                     # a list for all the alpha variables we get
        for i in self.hull.simplices:                  # Loops for all the simplexes
            points = []                                # A list for all the points coordinates
            for m in i:                                # Loops through all the index's and find the coordinates
                points.append(new_points[m])
            point = np.array(points)                   # converts to numpy array
            n = self.find_plane(point)                 # Find the normal and distance
            x = self.get_alpha(d, center, n)           # Finds the alpha value
            if 0 <= x <= 1:                            # If alpha between 0 and 1 it gets added to the alpha list
                if self.in_triangle(point, self.line_alpha(x, d, center)):  # And if its in the triangle to
                    alpha.append(x)
        a = np.array(alpha)
        np.sort(a, axis=0)
        nearest_point = self.line_alpha(a[0], d, center)
        return nearest_point

    def line_alpha(self, alpha, d, center):
        """Equation for calculating the nearest point

        :param alpha: float
            The highest given alpha value
        :param d: ndarray
            The start point.
        :param center: ndarray
            The center is a end point in the color space.
        :return: ndarray
            Return the nearest point.
        """
        nearest_point = alpha * np.array(d) + center \
            - alpha * np.array(center)     # finds the coordinates for the nearest point
        return nearest_point
