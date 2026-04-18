import Foundation
import ARKit

class GestureManager {
    static let shared = GestureManager()
    
    var isLeftEyeBlinking: Bool = false
    var isRightEyeBlinking: Bool = false
    var isJawOpen: Bool = false
    
    func update(with faceAnchor: ARFaceAnchor) {
        let blendShapes = faceAnchor.blendShapes
        
        if let leftBlink = blendShapes[.eyeBlinkLeft]?.floatValue {
            isLeftEyeBlinking = leftBlink > 0.3
        }
        
        if let rightBlink = blendShapes[.eyeBlinkRight]?.floatValue {
            isRightEyeBlinking = rightBlink > 0.3
        }
        
        if let jawOpen = blendShapes[.jawOpen]?.floatValue {
            isJawOpen = jawOpen > 0.4
        }
    }
    
    func isDoubleBlinking() -> Bool {
        return isLeftEyeBlinking && isRightEyeBlinking
    }
    
    func isSingleBlink() -> Bool {
        return isLeftEyeBlinking || isRightEyeBlinking
    }

    func isAnyEyeBlinking() -> Bool {
        return isLeftEyeBlinking || isRightEyeBlinking
    }
}
