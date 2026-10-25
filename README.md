# Ellipse focus simulation

*Every direction. One destination.*

An interactive simulation of a special property of ellipses: a ball sent out
from one focus reflects off the wall and passes through the other focus,
regardless of its launch direction.

<img width="800" height="450" alt="Image" src="https://github.com/user-attachments/assets/5d7032c4-b37a-4057-9d83-aea206cde810" />

## What it shows

The two gold markers are the ellipse's **foci**. Balls leave a focus in different
directions, bounce off the boundary, and meet at the opposite focus. Although
their routes look different, they all cover the same distance. Balls launched
together at the same speed therefore arrive together.

Click inside the ellipse to aim a ball from the nearest focus, or use **Launch**
to send out a group. Change the ellipse's shape and playback speed to explore
the patterns. Rainbow trails reveal the paths, and yellow flashes mark wall hits.


With **Duplicate each pass** enabled, each ball splits into two at the next
focus, spreading symmetrically around its return direction. The population grows
from 1 to 2, 4, 8, and so on, up to the chosen limit. Without duplication, balls
retrace their routes. These focus turnarounds and splits are animation rules;
the wall bounces follow the reflection law. Balls pass through each other.

## The maths

An ellipse with horizontal semimajor axis **a** and vertical semiminor axis **b**
has the equation

$$
\frac{x^2}{a^2} + \frac{y^2}{b^2} = 1.
$$

Its foci lie at $(\pm c, 0)$, where $c = \sqrt{a^2-b^2}$. The
**eccentricity**, $e = c/a$, describes its shape: values near 0 are almost
circular, while values near 1 produce a long, narrow ellipse. This simulation
uses $a = 1$, so $b = \sqrt{1-e^2}$ and the foci are at $(\pm e, 0)$.

For any point **P** on the boundary, the distances to the two foci satisfy

$$
|F_1P| + |PF_2| = 2a.
$$

That constant distance explains the simultaneous arrivals. The ellipse's wall
also makes equal angles with the incoming and outgoing paths, so an ordinary
reflection sends a ball from one focus toward the other.

The simulation calculates each bounce using the incoming velocity **v** and the
wall's outward unit normal **n**:

$$
\mathbf{v}_{\text{out}} = \mathbf{v} - 2(\mathbf{v}\cdot\mathbf{n})\mathbf{n}.
$$

This reverses the velocity component perpendicular to the wall while preserving
the component along it and the ball's speed.
